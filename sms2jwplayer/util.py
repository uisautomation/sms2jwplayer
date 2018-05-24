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


def key_for_clip_id(clip_id, client=None):
    """
    :param clip_id: clip id of the SMS item to match the JWPlatform video
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.
    :raises: :py:class:`.VideoNotFoundError`
        if the clip id does not correspond to a JWPlatform video.
    :return: The key of a JWPlatform video matching the clip id
    """
    video = resource_for_entity_id('videos', 'clip', clip_id, client)

    # If no channel found, raise error
    if video is None:
        raise VideoNotFoundError()

    # Check the channel we found has a non-None key
    if video.get('key') is None:
        raise VideoNotFoundError()

    return video['key']


def key_for_media_id(media_id, client=None):
    """
    :param media_id: media id of the SMS item to match the JWPlatform video
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.
    :raises: :py:class:`.VideoNotFoundError`
        if the clip id does not correspond to a JWPlatform video.
    :return: The key of a JWPlatform video matching the media id
    """
    """
    :param media_id: the SMS media id of the required video
    :type media_id: int
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.

    """
    video = resource_for_entity_id('videos', 'media', media_id, client)

    # If no channel found, raise error
    if video is None:
        raise VideoNotFoundError()

    # Check the channel we found has a non-None key
    if video.get('key') is None:
        raise VideoNotFoundError()

    return video['key']


class ChannelNotFoundError(RuntimeError):
    """
    The provided SMS collection id does not have a corresponding JWPlatform channel.
    """


def key_for_collection_id(collection_id, client=None):
    """
    :param collection_id: collection id of the SMS item to match the JWPlatform video
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.
    :raises: :py:class:`.ChannelNotFoundError`
        if the clip id does not correspond to a JWPlatform channel.
    :return: The key of a JWPlatform channel matching the collection id
    """
    channel = resource_for_entity_id('channels', 'collection', collection_id, client)

    # If no channel found, raise error
    if channel is None:
        raise ChannelNotFoundError()

    # Check the channel we found has a non-None key
    if channel.get('key') is None:
        raise ChannelNotFoundError()

    return channel['key']


def resource_for_entity_id(resource_type, entity_type, id, client=None):
    """
    Retrieve JWPlatform resource matching an SMS entity id stored in it's custom params

    :param resource_type: the type of the JWPlatform resource
    :param entity_type: the type of the SMS entity
    :param id: the SMS entity id
    :param client: (options) an authenticated JWPlatform client as returned by
        :py:func:`.get_jwplatform_client`. If ``None``, call :py:func:`.get_jwplatform_client`.
    :return: The JWPlatform resource matching the SMS entity id or None
    """
    client = client if client is not None else get_jwplatform_client()

    # The name & value of the sms_*_id custom property we search for
    entity_id_name = 'sms_{}_id'.format(entity_type)
    entity_id_value = '{}:{:d}:'.format(entity_type, id)

    # Search for resources
    response = getattr(client, resource_type).list(**{
        'search:custom.' + entity_id_name: entity_id_value,
    })

    # Find all resources with matching entity id
    matching = [
        resource for resource in response.get(resource_type, [])
        if resource.get('custom', {}).get(entity_id_name) == entity_id_value
    ]

    if len(matching) == 0:
        # no matches are found
        return None

    if len(matching) > 1:
        # too many matches are found
        LOG.warning('{} {} matches at least 2 {}'.format(entity_type, id, resource_type))

    return matching[0]


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
