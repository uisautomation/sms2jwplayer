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
        "type": "videos",  // or "thumbnails", etc
        "resource: {
            // dictionary of resource properties
        }
    }

The Update object specifies a list of JWPlatform resources which need to be updated:

.. code:: js

    {
        "type": "videos",  // or "thumbnails", etc
        "resource": {
            // dictionary of properties to update
        }
    }

The Delete object specifies a list of JWPlatform resources which need to be deleted:

.. code:: js

    {
        "type": "videos",  // or "thumbnails", etc
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
MAX_ATTEMPTS = 10


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


def create_calls(client, updates):
    """
    Return an iterator of callables representing the API calls for each create job.
    """
    for update in updates:
        type_, resource = update.get('type'), update.get('resource', {})

        if type_ == 'videos':
            params = resource_to_params(resource)

            # We wrap the entire create/update process in a function since we make use of two API
            # calls (one is via key_for_media_id). Hence we want to re-try the entire thing if we
            # hit the API rate limit.
            def do_create():
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
                        # Attempt to find a matching video for this media id. If None found, that's
                        # OK.
                        try:
                            video_key = util.key_for_media_id(media_id)
                        except util.VideoNotFoundError:
                            pass

                if video_key is not None:
                    LOG.warning('Updating video %(video_key)s instead of creating new one',
                                {'video_key': video_key})
                    return client.videos.update(
                        http_method='POST', video_key=video_key, **params)
                else:
                    return client.videos.create(http_method='POST', **params)

            yield do_create
        else:
            LOG.warning('Skipping unknown update type: %s', type_)


def update_calls(client, updates):
    """
    Return an iterator of callables representing the API calls for each update job.
    """
    for update in updates:
        type_, resource = update.get('type'), update.get('resource', {})

        if type_ == 'videos':
            yield lambda: client.videos.update(http_method='POST', **resource_to_params(resource))
        else:
            LOG.warning('Skipping unknown update type: %s', type_)


def delete_calls(client, deletes):
    """
    Return an iterator of callables representing the API calls for each delete job.
    """
    for delete in deletes:
        type_, resource = delete.get('type'), delete.get('resource', {})

        if type_ == 'videos':
            yield lambda: client.videos.delete(http_method='POST', **resource_to_params(resource))
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
    delay = 0.1  # seconds

    for api_call in call_iterable:
        for _ in range(MAX_ATTEMPTS):
            try:
                yield api_call()

                # On a successful call, slightly shorten the delay
                delay = max(1e-2, min(2., delay * 0.8))
                time.sleep(delay)
                break
            except JWPlatformRateLimitExceededError:
                delay = max(1e-2, min(2., 2. * delay))


def resource_to_params(resource):
    def iterate(d, prefix=''):
        for k, v in d.items():
            if isinstance(v, dict):
                for p in iterate(v, prefix+k+'.'):
                    yield p
            else:
                yield (prefix+k, v)
    return dict(iterate(resource))
