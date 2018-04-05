"""
The genupdatejob subcommand examines video metadata from jwplayer and the current SMS export and
generates a list of updates which should be applied.

It outputs a single JSON object with the following schema:

.. code:: js

    {
        "create": List<Create>,
        "update": List<Update>
    }

The Create object specifies a list of JWPlatform resources which should be created:

.. code:: js

    {
        "type": { "videos", "thumbnails", ... }
        "resource: {
            // dictionary of resource properties
        }
    }

The Update object specifies a list of JWPlatform resources which need to be updated:

.. code:: js

    {
        "type": { "videos", "thumbnails", ... }
        "resource": {
            // dictionary of properties to update
        }
    }

"""
import json
import logging
import re
import urllib.parse
import dateutil.parser

from sms2jwplayer.institutions import INSTIDS
from . import csv as smscsv
from .util import output_stream, get_key_path, parse_custom_prop


LOG = logging.getLogger(__name__)


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
        process_videos(opts, fobj, items, videos)


def process_videos(opts, fobj, items, videos):
    """
    Process video metadata records with reference to a dictionary of media items keyed by the
    stripped path. Write results to file as JSON document.

    """
    # Statistics we record
    n_skipped = 0

    # The list of create, update and delete jobs which need to be performed.
    creates, updates = [], []

    # A set of item media_ids which could not be matched to a corresponding JWPlatform video. This
    # starts full of all items but items are removed as matching happens.
    new_media_ids = set([item.media_id for item in items.values()])

    # A set of clip ids which already exist in JWPlatform
    existing_clip_ids = set()

    # A list of JWPlatform video resources which could not be matched to an SMS media object and
    # hence should be deleted.
    unmatched_videos = []

    # A list of (item, video resource) tuples representing that a given SMS media item is
    # represented by a JWPlatform video resource. This may be a one-to-many mapping; a single SMS
    # media item may have more than one JWPlatform video resource associated with it.
    associations = []

    # A dictionary which allows retrieving media items by clip id. Stores an (item, path) tuple.
    items_by_clip_id = dict((item.clip_id, (item, path)) for path, item in items.items())

    # A dictionary, keyed by media id, of sequences of items associated with that media
    items_by_media_id = {}
    for _, item in items.items():
        media_items = items_by_media_id.get(item.media_id, list())
        media_items.append(item)
        items_by_media_id[item.media_id] = media_items

    # Match jwplayer videos to SMS items
    for video in videos:
        # Find an existing SMS clip id
        clip_id_prop = get_key_path(video, 'custom.sms_clip_id')
        if clip_id_prop is None:
            n_skipped += 1
            continue

        # Retrieve the matching SMS media item (or record the inability to do so)
        try:
            item, _ = items_by_clip_id[int(parse_custom_prop('clip', clip_id_prop))]
        except KeyError:
            unmatched_videos.append(video)
            continue

        # Remove matched item from new_items set
        new_media_ids -= {item.media_id}
        existing_clip_ids.add(item.clip_id)

        # We now have a match between a video and SMS media item. Record the match.
        associations.append((item, video))

    # Generate updates for existing videos
    for item, video in associations:
        expected_video = video_resource(opts, item)

        # Calculate delta from resource which exists to expected resource
        delta = updated_keys(video, expected_video)
        if len(delta) > 0:
            # The delta is non-empty, so construct an update request. FSR, the *update* request for
            # JWPlatform requires the video be specified via 'video_key' but said key appears in
            # the video resource returned by /videos/list as 'key'.
            update = {'video_key': video['key']}
            update.update(delta)
            updates.append({
                'type': 'videos',
                'resource': update,
            })

    # Generate creates for new videos
    create_clip_ids = set()
    for media_items in (items_by_media_id[media_id] for media_id in new_media_ids):
        video_item, audio_item = None, None
        for item in media_items:
            if item.format is smscsv.MediaFormat.VIDEO:
                video_item = item
            elif item.format is smscsv.MediaFormat.AUDIO:
                audio_item = item
            else:
                LOG.warning('Unknown format: %s', item.format)

        # Prefer video items over audio ones
        item = video_item if video_item is not None else audio_item

        if item is None:
            LOG.warning('Could not match items %s to video or audio clip', [
                i.clip_id for i in media_items
            ])
            continue

        # If we've ended up with an existing clip, don't bother
        if item.clip_id in existing_clip_ids or item.clip_id in create_clip_ids:
            continue

        create_clip_ids.add(item.clip_id)

        video = video_resource(opts, item)
        video.update({
            'download_url': url(opts, item),
        })
        creates.append({
            'type': 'videos',
            'resource': video,
        })

    LOG.info('Number of JWPlatform videos matched to SMS media items: %s', len(associations))
    LOG.info('Number of SMS media items with no existing video: %s', len(new_media_ids))
    LOG.info('Number of JWPlatform videos not matched to SMS media items: %s',
             len(unmatched_videos))
    LOG.info('Number of JWPlatform videos with no import URL: %s', n_skipped)
    LOG.info('Number of video creations: %s', len(creates))
    LOG.info('Number of video updates: %s', len(updates))

    json.dump({'create': creates, 'update': updates}, fobj)


def updated_keys(source, target):
    """Return a dict which is the delta between source and target. Keys in target which have
    different values or do not exist in source are returned.

    """
    # Initially, the delta is empty
    delta = {}

    for key, value in target.items():
        try:
            source_value = source[key]
        except KeyError:
            # Key is not in source, set it in delta
            delta[key] = source_value
        else:
            # Key is in source
            if isinstance(value, dict):
                # Value is itself a dict so recurse
                sub_delta = updated_keys(source_value, value)
                if len(sub_delta) > 1:
                    delta[key] = sub_delta
            elif value != source_value:
                # Value differs between source and target. Return delta.
                delta[key] = value

    return delta


def video_resource(opts, item):
    """
    Construct what the JWPlatform video resource for a SMS media item should look like.

    """
    # Custom props
    custom_props = custom_props_for_item(item)

    # Start making the video resource
    resource = {
        "custom": custom_props,
    }

    # Add title and description if present
    for key, value in (('title', item.title), ('description', item.description)):
        value = sanitise(value)
        if value.strip() != '':
            resource[key] = value

    # Add a created at date
    created_at = custom_props.get('sms_created_at')
    if created_at is not None:
        date_str = ':'.join(created_at.split(':')[1:-1])
        resource['date'] = int(dateutil.parser.parse(date_str).timestamp())

    return resource


def custom_props_for_item(item):
    """
    Return a dictionary of custom props which should be set on a particular video item.

    """
    # form list of expected custom properties. We cuddle the id numbers in <type>:...: so that
    # we can search for "exactly" the media id or clip id rather than simply a video whose id
    # contains another. (E.g. searching for clip "10" is likely to being up "210", "310",
    # "1045", etc.)
    return {
        'sms_media_id': 'media:{}:'.format(item.media_id),
        'sms_clip_id': 'clip:{}:'.format(item.clip_id),
        # format - migration not required
        # filename - migration not required
        'sms_created_at': 'created_at:{}:'.format(item.created_at.isoformat()),
        # title - migrated as media item title
        # description - migrated as media item description
        'sms_collection_id': 'collection:{}:'.format(item.collection_id),
        'sms_instid': 'instid:{}:'.format(item.instid),
        'sms_aspect_ratio': 'aspect_ratio:{}:'.format(item.aspect_ratio),
        'sms_created_by': 'created_by:{}:'.format(item.creator),
        # in_dspace - migration not required
        'sms_publisher': 'publisher:{}:'.format(item.publisher),
        'sms_copyright': 'copyright:{}:'.format(item.copyright),
        'sms_language': 'language:{}:'.format(item.language),
        'sms_keywords': 'keywords:{}:'.format(item.keywords),
        # visibility - migration merged with sms_acl
        'sms_acl': 'acl:{}:'.format(convert_acl(item.visibility, item.acl)),
        'sms_screencast': 'screencast:{}:'.format(item.screencast),
        'sms_image_id': 'image_id:{}:'.format(item.image_id),
        # dspace_path - migration not required
        'sms_featured': 'featured:{}:'.format(item.featured),
        'sms_branding': 'branding:{}:'.format(item.branding),
        'sms_last_updated_at': 'last_updated_at:{}:'.format(item.last_updated_at),
        'sms_updated_by': 'updated_by:{}:'.format(item.updated_by),
        'sms_downloadable': 'downloadable:{}:'.format(item.downloadable),
        'sms_withdrawn': 'withdrawn:{}:'.format(item.withdrawn),
        # abstract - migration impractical
        # priority - migration not required
    }


# A regex pattern for CRSID matching.
CRSID_PATTERN = re.compile("^[A-Za-z]+[0-9]+$")


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
                new_acl.append('GROUP_{}'.format(ace))
            elif ace.upper() in INSTIDS:
                new_acl.append('INST_{}'.format(ace.upper()))
            elif CRSID_PATTERN.match(ace):
                new_acl.append('USER_{}'.format(ace))
            else:
                LOG.warning('The ACE "{}" cannot be resolved'.format(ace))

    return ",".join(new_acl)


def url(opts, item):
    """Return the URL for an item."""
    path_items = item.filename.strip('/').split('/')
    path_items = path_items[int(opts['--strip-leading']):]
    return urllib.parse.urljoin(opts['--base'] + '/', '/'.join(path_items))


def image_url(opts, item):
    """Return the URL for an image_id."""
    return urllib.parse.urljoin(opts['--base-image-url'], str(item.image_id)+".jpg")


def sanitise(s, max_length=4096):
    """
    Strip odd characters from a string and sanitise the length to avoid JWPlatform complaining.

    """
    # Map control characters to empty string
    s = s.translate(dict.fromkeys(range(32)))

    # Truncate
    s = s[:max_length]
    return s
