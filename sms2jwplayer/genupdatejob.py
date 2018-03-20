"""
The genupdatejob subcommand examines video metadata from jwplayer and the current SMS export and
generates a list of updates which should be applied.

It outputs a single JSON object with the following schema:

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
from urllib.parse import urlsplit

from . import csv as smscsv
from .util import output_stream, get_key_path


LOG = logging.getLogger('genmrss')


def main(opts):
    videos = []
    for metadata_fn in opts['<metadata>']:
        with open(metadata_fn) as f:
            videos.extend(json.load(f).get('videos', []))
    LOG.info('Loaded metadata for %s videos', len(videos))

    # Load items keyed by stripped path
    strip_from = int(opts['--strip-leading'])
    LOG.info('Stripping leading %s component(s) from filename', strip_from)
    with open(opts['<csv>']) as f:
        items = dict(
            ('/'.join(item.filename.strip('/').split('/')[strip_from:]), item)
            for item in smscsv.load(f)
        )
    LOG.info('Loaded %s media item(s) from export', len(items))

    with output_stream(opts) as fobj:
        process_videos(fobj, items, videos)


def convert_acl(visibility, acl):
    """
    Converts the old visibility and acl fields of :py:`~csv.MediaItem` to the new ACL scheme as
    defined here: :py:`~csv.MediaItem.acl`.

    :param visibility: :py:`~csv.MediaItem.visibility`
    :param acl: :py:`~csv.MediaItem.acl` (list)
    :return: the converted ACL
    """
    new_acl = []

    def has_acl():
        """Captures the case where the ACL [''] means no ACL """
        return len(acl) != 1 or acl[0] if acl else False

    if visibility == 'world-overrule' or (visibility == 'world' and not has_acl()):
        new_acl.append('WORLD')
    elif visibility == 'cam-overrule' or (visibility == 'cam' and not has_acl()):
        new_acl.append('CAM')

    if has_acl():
        for ace in acl:
            if ace.isdigit():
                new_acl.append(f'GROUP_{ace}')
            elif ace.upper() == ace:
                # Testing if a string is uppercase to decide if it represents an institution.
                # TODO Is this safe? Works for all data as at 2018/03/20.
                # Otherwise we need to use lookup.
                new_acl.append(f'INST_{ace}')
            else:
                new_acl.append(f'USER_{ace}')

    return ",".join(new_acl)


def process_videos(fobj, items, videos):
    """
    Process video metadata records with reference to a dictionary of media items keyed by the
    stripped path. Write results to file as JSON document.

    """
    # Statistics we record
    n_skipped = 0
    n_unmatched = 0
    n_matched = 0

    updates = []

    # Match jwplayer videos to SMS items
    for video in videos:
        # Find original fetch URL
        orig_url = get_key_path(video, 'custom.import_guid')
        if orig_url is None:
            n_skipped += 1
            continue

        # Parse path components
        path_components = urlsplit(orig_url).path.split('/')

        # Try to find item by joining path components
        item = None
        while len(path_components) > 0 and item is None:
            item = items.get('/'.join(path_components))
            path_components = path_components[1:]

        if item is None:
            n_unmatched += 1
            continue

        # video and item now match
        n_matched += 1

        # form list of expected custom properties. We cuddle the id numbers in <type>:...: so that
        # we can search for "exactly" the media id or clip id rather than simply a video whose id
        # contains another. (E.g. searching for clip "10" is likely to being up "210", "310",
        # "1045", etc.)
        custom_props = {
            'sms_media_id': f'media:{item.media_id}:',
            'sms_clip_id': f'clip:{item.clip_id}:',
            # format - migration not required
            # filename - migration not required
            'sms_created_at': f'created_at:{item.created_at.isoformat()}:',
            # title - migrated as media item title
            # description - migrated as media item description
            'sms_collection_id': f'collection:{item.collection_id}:',
            'sms_instid': f'instid:{item.instid}:',
            'sms_aspect_ratio': f'aspect_ratio:{item.aspect_ratio}:',
            'sms_created_by': f'created_by:{item.creator}:',
            # in_dspace - migration not required
            'sms_publisher': f'publisher:{item.publisher}:',
            'sms_copyright': f'copyright:{item.copyright}:',
            'sms_language': f'language:{item.language}:',
            'sms_keywords': f'keywords:{item.keywords}:',
            # visibility - migration merged with sms_acl
            'sms_acl': f'acl:{convert_acl(item.visibility, item.acl)}:',
            'sms_screencast': f'screencast:{item.screencast}:',
            'sms_image_id': f'image_id:{item.image_id}:',
            # dspace_path - migration not required
            'sms_featured': f'featured:{item.featured}:',
            'sms_branding': f'branding:{item.branding}:',
            'sms_last_updated_at': f'last_updated_at:{item.last_updated_at}:',
            'sms_updated_by': f'updated_by:{item.updated_by}:',
            'sms_downloadable': f'downloadable:{item.downloadable}:',
            'sms_withdrawn': f'withdrawn:{item.withdrawn}:',
            # abstract - migration impractical
            # priority - migration not required
        }

        # remove those which match
        for k, v in list(custom_props.items()):
            if get_key_path(video, 'custom.' + k) == v:
                del custom_props[k]

        # write a row if there is work to do
        if len(custom_props) > 0:
            updates.append({'key': get_key_path(video, 'key'), 'custom': custom_props})

    LOG.info('Number of jwplayer videos matched to SMS media items: %s', n_matched)
    LOG.info('Number of jwplayer videos not matched to SMS media items: %s', n_unmatched)
    LOG.info('Number of jwplayer videos with no import URL: %s', n_skipped)
    LOG.info('Number of video updates: %s', len(updates))

    json.dump({'updates': updates}, fobj)
