"""
The :py:mod:`~sms2jwplayer.util` module contains general utility functions for the rest of the
program to use.

"""

import contextlib
import os
import re
import sys

import jwplatform


#: regex for parsing a custom prop field
CUSTOM_PROP_VALUE_RE = re.compile(r'^([a-z][a-z0-9_]*):(.*):$')


class JWPlatformClientError(RuntimeError):
    """
    An error which is thrown if appropriate credentials for the jwplatform cannot be found in the
    environment.

    """
    pass


def get_jwplatform_client():
    """
    Examine the environment and return an authenticated jwplatform.Client instance. Raises
    JWPlatformClientError if credentials are not available

    """
    api_key = os.environ.get('JWPLAYER_API_KEY')
    if api_key is None:
        raise JWPlatformClientError('Set jwplayer API key in JWPLAYER_API_KEY environment '
                                    'variable')

    api_secret = os.environ.get('JWPLAYER_API_SECRET')
    if api_secret is None:
        raise JWPlatformClientError('Set jwplayer API secret in JWPLAYER_API_SECRET environment '
                                    'variable')

    return jwplatform.Client(api_key, api_secret)


@contextlib.contextmanager
def output_stream(opts, opt_key='--output'):
    """
    Given the docopt options dictionary, yield a file-like object suitable for writing output to.
    *opt_key* is the key used to retrieve the output file from the options.

    """
    out_file = opts[opt_key]

    if out_file is None:
        yield sys.stdout
    else:
        with open(out_file, 'w') as fobj:
            yield fobj


@contextlib.contextmanager
def input_stream(opts, opt_key):
    """
    Given the docopt options dictionary, yield a file-like object suitable for reading input from.
    *opt_key* is the key used to retrieve the input file from the options.

    """
    in_file = opts[opt_key]

    if in_file is None:
        yield sys.stdin
    else:
        with open(in_file) as fobj:
            yield fobj


def get_key_path(obj, keypath):
    """
    Given a dotted key path like "a.b.c", attempt to retrieve obj["a"]["b"]["c"]. If there is no
    such key at any stage, return None

    """
    for key in keypath.split('.'):
        if obj is None:
            return None
        obj = obj.get(key)
    return obj


def parse_custom_prop(expected_type, field):
    """
    Parses a custom prop content of the form "<type>:<value>:". Returns the value tuple.
    Raises ValueError if the field is of the wrong form or has wrong type.

    """
    match = CUSTOM_PROP_VALUE_RE.match(field)
    if not match:
        raise ValueError('Field has invalid format: {field}'.format(field=field))
    prop_type, value = match.groups()
    if prop_type != expected_type:
        raise ValueError(
            'Field has unexpected type "{prop_type}". Expected "{expected_type}".'.format(
                prop_type=prop_type, expected_type=expected_type
            ))
    return value


class VideoNotFoundError(RuntimeError):
    """
    The provided SMS media ID does not have a corresponding JWPlatform video.
    """


def key_for_media_id(media_id, preferred_media_type='video', client=None):
    """
    :param media_id: the SMS media ID of the required video
    :type media_id: int
    :param preferred_media_type: (optional) the preferred media type to return. One of ``'video'``
        or ``'audio'``.
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.
    :raises: :py:class:`.VideoNotFoundError` if the media id does not correspond to a JWPlatform
        video.

    """
    client = client if client is not None else get_jwplatform_client()

    # The value of the sms_media_id custom property we search for
    media_id_value = 'media:{:d}:'.format(media_id)

    # Search for videos
    response = client.videos.list(**{
        'search:custom.sms_media_id': media_id_value,
    })

    # Loop through "videos" to find the preferred one based on mediatype
    video_resource = None
    for video in response.get('videos', []):
        # Sanity check: skip videos with wrong media id since video search is
        # not "is equal to", it is "contains".
        if video.get('custom', {}).get('sms_media_id') != media_id_value:
            continue

        # use this video if it has the preferred mediatype or if we have nothing
        # else
        if (video.get('mediatype') == preferred_media_type
                or video_resource is None):
            video_resource = video

    # If no video found, raise error
    if video_resource is None:
        raise VideoNotFoundError()

    # Check the video we found has a non-None key
    if video_resource.get('key') is None:
        raise VideoNotFoundError()

    return video_resource['key']
