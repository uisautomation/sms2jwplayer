"""
The fetch subcommand fetches metadata on jwplayer videos and stores it locally in JSON documents.

"""
import json
import logging
import sys

from .util import get_jwplatform_client, JWPlatformClientError


LOG = logging.getLogger('fetch')


def main(opts):
    try:
        client = get_jwplatform_client()
    except JWPlatformClientError as e:
        LOG.error('jwplatform error: %s', e)
        sys.exit(1)

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
