"""
The :py:mod:`~sms2jwplayer.util` module contains general utility functions for the rest of the
program to use.

"""

import contextlib
import logging
import os
import re
import sys
import urllib

import jwplatform
import requests
import time

from sms2jwplayer.csv import MediaItem, CollectionItem

LOG = logging.getLogger(__name__)

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
    The provided SMS media id does not have a corresponding JWPlatform video.
    """


def key_for_media_id(media_id, preferred_media_type='video', client=None):
    """
    :param media_id: the SMS media id of the required video
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


def channel_for_collection_id(collection_id, client=None):
    """
    :param collection_id: the SMS collection id of the required channel
    :type collection_id: int
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.
    :raises: :py:class:`.ChannelNotFoundError` if the collection id does not correspond to a
        JWPlatform channel.

    """
    client = client if client is not None else get_jwplatform_client()

    # The value of the sms_media_id custom property we search for
    collection_id_value = 'collection:{:d}:'.format(collection_id)

    # Search for channels
    response = client.channels.list(**{
        'search:custom.sms_collection_id': collection_id_value,
    })

    # Find all channels with matching collection id
    matching = [
        channel for channel in response.get('channels', [])
        if channel.get('custom', {}).get('sms_collection_id') == collection_id_value
    ]

    if len(matching) == 0:
        # no matches are found
        return None

    if len(matching) > 1:
        # too many matches are found
        LOG.warning('Collection {} matches more than one channel'.format(collection_id))

    return matching[0]


class ChannelNotFoundError(RuntimeError):
    """
    The provided SMS collection id does not have a corresponding JWPlatform channel.
    """


def key_for_collection_id(collection_id, client=None):
    """
    :param collection_id: the SMS collection id of the required channel
    :type collection_id: int
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.
    :raises: :py:class:`.ChannelNotFoundError` if the collection id does not correspond to a
        JWPlatform channel.

    """
    channel_resource = channel_for_collection_id(collection_id, client)

    # If no channel found, raise error
    if channel_resource is None:
        raise ChannelNotFoundError()

    # Check the channel we found has a non-None key
    if channel_resource.get('key') is None:
        raise ChannelNotFoundError()

    return channel_resource['key']


def upload_thumbnail_from_url(video_key, image_url, delay=None, client=None):
    """
    Updates the thumbnail for a particular video object with the image at image_url.

    :param video_key: <string> Video's object ID. Can be found within JWPlayer Dashboard.
    :param image_url: The public URL on the image to use as a thumbnail
    :param delay: delay (in seconds) to apply between API calls
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.
    """
    client = client if client is not None else get_jwplatform_client()

    response = client.videos.thumbnails.update(video_key=video_key)
    if delay:
        time.sleep(delay)

    # construct base url for upload
    url = '{0[protocol]}://{0[address]}{0[path]}'.format(response['link'])

    # add required 'api_format' to the upload query params
    response['link']['query']['api_format'] = 'json'

    files = {'file': urllib.request.urlopen(image_url)}

    return requests.post(url, params=response['link']['query'], files=files).json()


DATA_TYPE_DICT = {
    'videos': ('videos', 'videos', MediaItem),
    'channels': ('channels', 'channels', CollectionItem),
    'videos_in_channels': ('videos_in_channels', 'channels', CollectionItem)
}


def get_data_type(opts):
    """Gets the type of JWPlayer data ('videos' or 'channels' or 'videos_in_channels')
    from the CL options"""
    return next(
        DATA_TYPE_DICT[data_type]
        for data_type in ('videos', 'channels', 'videos_in_channels')
        if opts.get(data_type, False)
    )
