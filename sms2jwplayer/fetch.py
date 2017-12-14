"""

"""
import json
import logging
import os
import sys

import jwplatform


LOG = logging.getLogger('fetch')


def main(opts):
    api_key = os.environ.get('JWPLAYER_API_KEY')
    if api_key is None:
        LOG.error('Set jwplayer API key in JWPLAYER_API_KEY environment '
                  'variable')
        sys.exit(1)

    api_secret = os.environ.get('JWPLAYER_API_SECRET')
    if api_secret is None:
        LOG.error('Set jwplayer API secret in JWPLAYER_API_SECRET environment '
                  'variable')
        sys.exit(1)

    client = jwplatform.Client(api_key, api_secret)

    current_offset = 0
    while True:
        LOG.info('Fetching videos starting from offset: %s', current_offset)
        results = client.videos.list(
            result_offset=current_offset, result_limit=1000)
        LOG.info('Got information on %s video(s)', len(results['videos']))

        # Stop when we get no results
        if len(results['videos']) == 0:
            LOG.info('Stopping')
            break

        out_pn = opts['--base-name'] + '{:06d}.json'.format(current_offset)
        LOG.info('Saving to: %s', out_pn)
        with open(out_pn, 'w') as fobj:
            json.dump(results, fobj)

        current_offset += len(results['videos'])
