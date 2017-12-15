"""
Apply update job as generated from genupdatejob. To avoid rate limit problems, calls to the
jwplayer API are performed with exponential backoff.

Takes as input a JSON document with the following schema.

.. code:: json

    {
        "updates": [
            ...
            {
                "key": <jwplayer key>,
                "custom": {
                    <dictionary of custom properties to set>
                }
            },
            ...
        ],
    }

"""
import json
import logging
import sys
import time

import tqdm
from jwplatform.errors import JWPlatformRateLimitExceededError

from .util import input_stream, get_jwplatform_client, JWPlatformClientError


LOG = logging.getLogger('applyupdatejob')

#: Maximum number of attempts on an API call before giving up
MAX_ATTEMPTS = 10


def main(opts):
    try:
        client = get_jwplatform_client()
    except JWPlatformClientError as e:
        LOG.error('jwplatform error: %s', e)
        sys.exit(1)

    with input_stream(opts, '<update>') as f:
        updates = json.load(f).get('updates', [])

    LOG.info('Update jobs to process: %s', len(updates))

    # If verbose flag is present, give a nice progress bar
    if opts['--verbose'] is not None:
        update_iterable = tqdm.tqdm(updates)
    else:
        update_iterable = updates

    # delay between calls to not hit rate limit
    delay = 0.1  # seconds

    for update in update_iterable:
        try:
            key = update['key']
        except KeyError:
            LOG.warning('Update lacks key: %s', repr(update))

        params = {'video_key': key}

        for custom_key, custom_value in update.get('custom', {}).items():
            params['custom.' + custom_key] = str(custom_value)

        for _ in range(MAX_ATTEMPTS):
            try:
                client.videos.update(**params)

                # On a successful call, slightly shorten the delay
                delay *= 0.95
                time.sleep(delay)
                break
            except JWPlatformRateLimitExceededError:
                delay *= 2.
