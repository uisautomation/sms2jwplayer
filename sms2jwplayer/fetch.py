"""
The fetch subcommand fetches metadata on jwplayer videos or channels
and stores it locally in JSON documents.

"""
import json
import logging
import sys

from .util import get_jwplatform_client, JWPlatformClientError, get_data_type

LOG = logging.getLogger(__name__)


def main(opts):
    try:
        client = get_jwplatform_client()
    except JWPlatformClientError as e:
        LOG.error('jwplatform error: %s', e)
        sys.exit(1)

    current_offset = 0
    _, data_type, _ = get_data_type(opts)
    while True:
        LOG.info('Fetching %s starting from offset: %s', data_type, current_offset)
        results = getattr(client, data_type).list(
            result_offset=current_offset, result_limit=1000)
        num_results = len(results[data_type])
        LOG.info('Got information on %s %s', num_results, data_type)

        # Stop when we get no results
        if num_results == 0:
            LOG.info('Stopping')
            break

        out_pn = opts['--base-name'] + '{:06d}.json'.format(current_offset)
        LOG.info('Saving to: %s', out_pn)
        with open(out_pn, 'w') as fobj:
            json.dump(results, fobj)

        current_offset += num_results
