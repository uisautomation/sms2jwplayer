"""
Apply update job as generated from genupdatejob. To avoid rate limit problems, calls to the
jwplayer API are performed with exponential backoff.

Takes as input a JSON document with the following schema.

.. code:: js

    {
        "create": List<Create>,
        "update": List<Update>
    }

The Create object specifies a list of JWPlatform resources which should be created:

.. code:: js

    {
        "type": "videos|channels",
        "resource: {
            // dictionary of resource properties
        }
    }

The Update object specifies a list of JWPlatform resources which need to be updated:

.. code:: js

    {
        "type": "videos|channels|image_load|image_load|image_check",
        "resource": {
            // dictionary of properties to update
        }
    }

The Delete object specifies a list of JWPlatform resources which need to be deleted:

.. code:: js

    {
        "type": "videos|channels",
        "resource": {
            // dictionary of parameters to delete request
        }
    }

"""
import json
import logging
import sys
import time

import tqdm
from jwplatform.errors import JWPlatformRateLimitExceededError

from . import util


LOG = logging.getLogger('applyupdatejob')

#: Maximum number of attempts on an API call before giving up
MAX_ATTEMPTS = 20

#: Maximum delay between each API call
MAX_DELAY = 2.0

#: Minimum delay between each API call
MIN_DELAY = 0.02


def main(opts):
    try:
        client = util.get_jwplatform_client()
    except util.JWPlatformClientError as e:
        LOG.error('jwplatform error: %s', e)
        sys.exit(1)

    with util.input_stream(opts, '<update>') as f:
        jobs = json.load(f)

    updates, creates, deletes = [jobs.get(k, []) for k in ['update', 'create', 'delete']]

    LOG.info('Number of update jobs to process: %s', len(updates))
    LOG.info('Number of create jobs to process: %s', len(creates))
    LOG.info('Number of delete jobs to process: %s', len(deletes))

    # If verbose flag is present, give a nice progress bar
    if opts['--verbose'] is not None:
        updates = tqdm.tqdm(updates)
        creates = tqdm.tqdm(creates)
        deletes = tqdm.tqdm(deletes)

    create_responses = list(
        execute_api_calls_respecting_rate_limit(create_calls(client, creates))
    )

    update_responses = list(
        execute_api_calls_respecting_rate_limit(update_calls(client, updates))
    )

    delete_responses = list(
        execute_api_calls_respecting_rate_limit(delete_calls(client, deletes))
    )

    if opts['--log-file'] is not None:
        with util.output_stream(opts, '--log-file') as f:
            json.dump({
                'create_responses': create_responses,
                'update_responses': update_responses,
                'delete_responses': delete_responses,
            }, f)


def videos_insert(client, delay, resource):
    """Inserts a video into a channel and updates the custom sms_media_ids param to reflect the new
    state of the channel."""
    try:
        video_key = util.key_for_media_id(resource['media_id'])
        time.sleep(delay)
    except util.VideoNotFoundError:
        return 'video not found for media_id: {}'.format(resource['media_id'])
    channel = util.channel_for_collection_id(resource['collection_id'], client)
    time.sleep(delay)
    if not channel:
        return 'channel not found for collection_id: {}'.format(resource['collection_id'])
    media_ids = get_media_ids_from_channel(channel)
    if resource['media_id'] in media_ids:
        # we do this in-case the job is accidentally run twice
        return 'video {} already in channel {}'.format(video_key, channel['key'])
    media_ids.add(resource['media_id'])
    response = client.channels.videos.create(channel_key=channel['key'], video_key=video_key)
    if response['status'] == 'ok':
        time.sleep(delay)
        return {'insert': response, 'update': update_media_ids(client, channel['key'], media_ids)}
    return response


def videos_delete(client, delay, resource):
    """Deletes a video from a channel and updates the custom sms_media_ids param to reflect the new
    state of the channel."""
    try:
        video_key = util.key_for_media_id(resource['media_id'])
        time.sleep(delay)
    except util.VideoNotFoundError:
        return 'video not found for media_id: ' + resource['media_id']
    channel = util.channel_for_collection_id(resource['collection_id'], client)
    time.sleep(delay)
    if not channel:
        return 'channel not found for collection_id: ' + resource['collection_id']
    media_ids = get_media_ids_from_channel(channel)
    if resource['media_id'] not in media_ids:
        # we do this in-case the job is accidentally run twice
        return 'video {} not in channel {}'.format(video_key, channel['key'])
    media_ids.remove(resource['media_id'])
    response = client.channels.videos.delete(channel_key=channel['key'], video_key=video_key)
    if response['status'] == 'ok':
        time.sleep(delay)
        return {'delete': response, 'update': update_media_ids(client, channel['key'], media_ids)}
    return response


def get_media_ids_from_channel(channel):
    """Retrieves the custom sms_media_ids param from a channel.."""
    default = {'sms_media_ids': 'media_ids::'}
    media_ids_prop = channel.get('custom', default).get('sms_media_ids', default['sms_media_ids'])
    media_ids = util.parse_custom_prop('media_ids', media_ids_prop)
    return set([] if media_ids == '' else [int(media_id) for media_id in media_ids.split(',')])


def update_media_ids(client, channel_key, media_ids):
    """Updates a channel with a new custom sms_media_ids param."""
    media_ids_string = ','.join(str(media_id) for media_id in media_ids)
    return client.channels.update(http_method='POST', **{
        'channel_key': channel_key,
        'custom.sms_media_ids': 'media_ids:{}:'.format(media_ids_string)
    })


def create_calls(client, creates):
    """
    Return an iterator of callables representing the API calls for each create job.
    """
    for create in creates:
        type_, resource = create.get('type'), create.get('resource', {})

        def log(response):
            return {'job': resource, 'log': response}

        if type_ == 'videos':
            params = resource_to_params(resource)

            # We wrap the entire create/update process in a function since we make use of two API
            # calls (one is via key_for_media_id). Hence we want to re-try the entire thing if we
            # hit the API rate limit.
            def do_create(delay):
                # If video_key is set to anything other than None, an update of that video key will
                # be done instead.
                video_key = None

                # See if the resource already exists. If so, perform an update instead.
                media_id_prop = params.get('custom.sms_media_id')
                if media_id_prop is not None:
                    try:
                        media_id = int(util.parse_custom_prop('media', media_id_prop))
                    except ValueError:
                        LOG.warning('Skipping video with bad media id prop: %s', media_id_prop)
                    else:
                        # Attempt to find a matching video for this media id.
                        # If None found, that's OK.
                        try:
                            video_key = util.key_for_media_id(media_id)
                        except util.VideoNotFoundError:
                            pass
                        finally:
                            time.sleep(delay)

                if video_key is not None:
                    LOG.warning('Updating video %(video_key)s instead of creating new one',
                                {'video_key': video_key})
                    return client.videos.update(
                        http_method='POST', video_key=video_key, **params)
                else:
                    return client.videos.create(http_method='POST', **params)

            yield do_create

        elif type_ == 'channels':
            params = resource_to_params(resource)

            # We wrap the entire create/update process in a function since we make use of two API
            # calls (one is via key_for_media_id). Hence we want to re-try the entire thing if we
            # hit the API rate limit.
            def do_create(delay):
                # If channel_key is set to anything other than None, an update of that channel key
                # will be done instead.
                channel_key = None

                # See if the resource already exists. If so, perform an update instead.
                collection_id_prop = params.get('custom.sms_collection_id')
                if collection_id_prop is not None:
                    try:
                        collection_id = int(util.parse_custom_prop(
                            'collection', collection_id_prop
                        ))
                    except ValueError:
                        LOG.warning(
                            'Skipping video with bad collection id prop: %s', collection_id_prop
                        )
                    else:
                        # Attempt to find a matching channel for this collection id.
                        # If None found, that's OK.
                        try:
                            channel_key = util.key_for_collection_id(collection_id)
                        except util.ChannelNotFoundError:
                            pass
                        finally:
                            time.sleep(delay)

                if channel_key is not None:
                    LOG.warning(
                        'Updating channel %(channel_key)s instead of creating new one',
                        {'channel_key': channel_key}
                    )
                    return client.channels.update(
                        http_method='POST', channel_key=channel_key, **params)
                else:
                    return client.channels.create(type='manual', http_method='POST', **params)

            yield do_create
        elif type_ == 'videos_insert':
            yield lambda delay: log(videos_insert(client, delay, resource))
        elif type_ == 'videos_delete':
            yield lambda delay: log(videos_delete(client, delay, resource))
        else:
            LOG.warning('Skipping unknown update type: %s', type_)


def update_calls(client, updates):
    """
    Return an iterator of callables representing the API calls for each update job.
    """
    for update in updates:
        type_, resource = update.get('type'), update.get('resource', {})

        def log(response):
            return {'job': resource, 'log': response}

        def image_load(delay):
            """
            uploads an SMS thumbnail image and, if successful, sets the custom 'image_status'
            parameter to 'loaded'
            """
            response = util.upload_thumbnail_from_url(client=client, **resource)
            if response['status'] == 'ok':
                time.sleep(delay)
                update_response = client.videos.update(http_method='POST', **{
                    'video_key': resource['video_key'],
                    'custom.sms_image_status': 'image_status:loaded:'
                })
                response = {
                    'upload': response,
                    'update': update_response
                }
            return log(response)

        def image_check(delay):
            """
            checks the status of an upload thumbnail image and records this status in the custom
            'image_status' parameter
            """
            response = client.videos.thumbnails.show(**resource)
            time.sleep(delay)
            status = response['thumbnail']['status']
            update_response = client.videos.update(http_method='POST', **{
                'video_key': resource['video_key'],
                'custom.sms_image_status': 'image_status:{}:'.format(status)
            })
            return log({'show': response, 'update': update_response})

        try:
            if type_ == 'videos':
                yield lambda delay: log(
                    client.videos.update(http_method='POST', **resource_to_params(resource))
                )
            elif type_ == 'channels':
                yield lambda delay: log(
                    client.channels.update(http_method='POST', **resource_to_params(resource))
                )
            elif type_ == 'videos_insert':
                yield lambda delay: log(videos_insert(client, delay, resource))
            elif type_ == 'videos_delete':
                yield lambda delay: log(videos_delete(client, delay, resource))
            elif type_ == 'image_load':
                yield image_load
            elif type_ == 'image_check':
                yield image_check
            else:
                LOG.warning('Skipping unknown update type: %s', type_)
        except JWPlatformRateLimitExceededError as e:
            raise JWPlatformRateLimitExceededError(
                "{}: {}: {}".format(type_, resource['video_key'], e.message)
            )


def delete_calls(client, deletes):
    """
    Return an iterator of callables representing the API calls for each delete job.
    """
    for delete in deletes:
        type_, resource = delete.get('type'), delete.get('resource', {})

        if type_ == 'videos':
            yield lambda delay: client.videos.delete(
                http_method='POST', **resource_to_params(resource)
            )
        else:
            LOG.warning('Skipping unknown delete type: %s', type_)


def execute_api_calls_respecting_rate_limit(call_iterable):
    """
    A generator which takes an iterable of callables which represent calls to the JWPlatform API
    and run them one after another. If a JWPlatformRateLimitExceededError is raised by the
    callable, exponentially back off and retry. Since retries are possible, callables from
    call_iterable may be called multiple times.

    Yields the results of calling the update job.

    """
    # delay between calls to not hit rate limit
    delay = MIN_DELAY  # seconds

    for api_call in call_iterable:
        error_message = None
        for _ in range(MAX_ATTEMPTS):
            try:
                yield api_call(delay)

                # On a successful call, slightly shorten the delay
                delay = max(MIN_DELAY, min(MAX_DELAY, delay * 0.2))
                time.sleep(delay)
                break
            except JWPlatformRateLimitExceededError as error:
                # On a rate limit failure, lengthen the delay
                delay = max(MIN_DELAY, min(MAX_DELAY, delay * 8.0))
                time.sleep(delay)
                error_message = error.message
        if error_message:
            yield "MAX_ATTEMPTS: " + error_message


def resource_to_params(resource):
    """
    flattens the keys of a dict:
        eg. converts {'a': {'x': 1, 'y': 2}, 'b': 3} to {'a.x': 1, 'a.y': 2, 'b': 3}
    """
    def iterate(d, prefix=''):
        for k, v in d.items():
            if isinstance(v, dict):
                for p in iterate(v, prefix+k+'.'):
                    yield p
            else:
                yield (prefix+k, v)
    return dict(iterate(resource))
