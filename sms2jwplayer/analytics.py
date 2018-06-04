"""
The analytics subcommand generates a CSV suitable for use inside the SMS representing stats from
jwplayer.

The JWPLAYER_API_KEY and JWPLAYER_API_ANALYTICS_SECRET environment variables must be set.

Output CSV headers:

    - clip_id
    - ip_addr
    - is_rtsp
    - is_itunes
    - media_id
    - collection_id
    - instid
    - format
    - quality
    - fetch_type
    - lat
    - long
    - is_cam
    - country
    - num_hits
    - num_bytes

"""
import collections
import csv
import datetime
import itertools
import logging
import os
import time
import sys

import requests
import tqdm

from .util import get_jwplatform_client, JWPlatformClientError
from jwplatform.errors import JWPlatformRateLimitExceededError, JWPlatformNotFoundError

LOG = logging.getLogger()

HEADERS = [
    'clip_id', 'ip_addr', 'is_rtsp', 'is_itunes', 'media_id', 'collection_id', 'instid',
    'format', 'quality', 'fetch_type', 'lat', 'long', 'is_cam', 'country', 'num_hits', 'num_bytes'
]

#: Maximum number of attempts on an API call before giving up
MAX_ATTEMPTS = 10

#: Map from jwplatform mediatype to SMS format
FORMAT_MAP = {'video': 'mp4', 'audio': 'mp3'}

AnalyticsRow = collections.namedtuple('AnalyticsRow', 'media_id country_code plays')
OutputRow = collections.namedtuple('OutputRow', HEADERS)


def main(opts):
    try:
        client = get_jwplatform_client()
    except JWPlatformClientError as e:
        LOG.error('jwplatform error: %s', e)
        sys.exit(1)

    api_key = os.environ.get('JWPLAYER_API_KEY', '')
    if api_key == '':
        LOG.error('JWPLAYER_API_KEY environment variable not set')
        sys.exit(1)

    api_secret = os.environ.get('JWPLAYER_API_ANALYTICS_SECRET', '')
    if api_secret == '':
        LOG.error('JWPLAYER_API_ANALYTICS_SECRET environment variable not set')
        sys.exit(1)

    target_date = datetime.datetime.strptime(opts['<date>'], '%Y-%m-%d').date().isoformat()

    rows = []
    for page in itertools.count():
        LOG.info('Fetching page index: %s', page)

        # Get next page of analytics
        response = get_analytics(api_key, api_secret, {
            'start_date': target_date,
            'end_date': target_date,
            'metrics': [{
                'operation': 'sum',
                'field': 'plays',
            }],
            'dimensions': ['media_id', 'country_code'],
            'sort': [{'field': 'plays', 'order': 'DESCENDING'}],
            'page': page,
            'page_length': 100,
        })

        # If we get no results, we're done
        n_rows = len(response['data']['rows'])
        if n_rows == 0:
            LOG.info('No rows returned, we are done')
            break

        # Otherwise parse rows
        LOG.info('Rows returned: %s', n_rows)
        column_headers = response['metadata']['column_headers']
        headings = column_headers['dimensions'] + column_headers['metrics']
        rows.extend([
            AnalyticsRow(**{
                dimension['field']: datum
                for dimension, datum in zip(headings, row)
            })
            for row in response['data']['rows']
        ])

    LOG.info('Got analytics for %s video(s)', len(rows))

    # If verbose flag is present, give a nice progress bar
    if opts['--verbose']:
        rows_iterable = tqdm.tqdm(rows)
    else:
        rows_iterable = rows

    if opts['--output'] is not None and opts['--output'] != '-':
        with open(opts['--output'], 'w') as fobj:
            write_output(fobj, client, rows_iterable)
    else:
        write_output(sys.stdout, client, rows_iterable)


def write_output(fobj, client, rows_iterable):
    csv_writer = csv.writer(fobj)
    csv_writer.writerow(HEADERS)

    LOG.info('Fetching video metadata')

    # delay between calls to not hit rate limit
    delay = 0.1  # seconds

    for row in rows_iterable:
        for _ in range(MAX_ATTEMPTS):
            try:
                try:
                    response = client.videos.show(video_key=row.media_id)
                except JWPlatformNotFoundError:
                    # the video could have been deleted
                    break

                if not response.get('status') == 'ok':
                    break

                # extract custom properties
                video = response.get('video', {})
                custom = video.get('custom', {})

                # get metadata for video
                metadata = {
                    'clip_id': custom.get('sms_clip_id', 'clip::').split(':')[1],
                    'media_id': custom.get('sms_media_id', 'media::').split(':')[1],
                    'collection_id': custom.get('sms_collection_id', 'collection::').split(':')[1],
                    'format': FORMAT_MAP.get(video.get('mediatype'), ''),
                    'country': row.country_code,
                }

                csv_writer.writerow(OutputRow(
                    ip_addr='127.0.0.1',
                    is_rtsp='f', is_itunes='f',
                    instid='', quality='high', fetch_type='stream',
                    lat='0', long='0', is_cam='f',
                    num_hits=row.plays, num_bytes=0,
                    **metadata
                ))

                # On a successful call, slightly shorten the delay
                delay = max(1e-2, min(2., delay * 0.8))
                time.sleep(delay)
                break
            except JWPlatformRateLimitExceededError:
                delay = max(1e-2, min(2., 2. * delay))


def get_analytics(api_key, api_secret, payload):
    r = requests.post(
        'https://api.jwplayer.com/v2/sites/' + api_key + '/analytics/queries/',
        json=payload, headers={'Authorization': api_secret})
    r.raise_for_status()
    return r.json()
