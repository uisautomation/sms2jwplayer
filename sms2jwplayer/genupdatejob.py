"""
The genupdatejob subcommand examines video metadata from jwplayer and the current SMS export and
generates a list of updates which should be applied. See the documentation for
:py:mod:`.applyupdatejob` for a description of the update job format.

"""
import json
import logging
import re
import urllib.parse
import dateutil.parser

from sms2jwplayer.institutions import INSTIDS
from . import csv as smscsv
from .util import output_stream, get_key_path, parse_custom_prop, get_data_type

LOG = logging.getLogger(__name__)


def main(opts):

    sub_cmd, data_type, item_type = get_data_type(opts)

    metadata = []
    for metadata_fn in opts['<metadata>']:
        with open(metadata_fn) as f:
            metadata.extend(json.load(f).get(data_type, []))
    LOG.info('Loaded metadata for %s %s', len(metadata), data_type)

    with open(opts['<csv>']) as f:
        items = smscsv.load(item_type, f)
    LOG.info('Loaded %s %s item(s) from export', len(items), item_type.__name__)

    with output_stream(opts) as fobj:
        globals()['process_' + sub_cmd](opts, fobj, items, metadata)


def generic_channels_processor(fobj, collections, channels, create, update):
    """
    Generic method that generates a set of create/update jobs for the purpose of synchronising
    an aspect of a set of JWPlayer channels with a set of SMS collections. The aspect to be
    synchronised is defined by the create/update callables. These jobs are written to file as
    JSON document.

    :param fobj: file to write the create/update jobs to
    :param collections: a list of SMS collections
    :param channels: a list of JWPlayer channels
    :param create: a callable that returns a list of create jobs
    :param update: a callable that returns a list of update jobs

    """
    # Statistics we record
    n_skipped = 0

    # The list of create and update jobs which need to be performed.
    creates, updates = [], []

    # A list of JWPlatform channel resources which could not be matched to an SMS collection object
    # and hence should be deleted.
    unmatched_channels = []

    # A list of (collection, channel resource) tuples representing that a given SMS collection is
    # represented by a JWPlatform channel resource.
    associations = []

    # A dictionary which allows retrieving collections by collection id.
    collections_by_id = dict((collection.collection_id, collection) for collection in collections)

    # A set of collection ids which could not be matched to a corresponding JWPlatform channel.
    # This starts with all collections but ids are removed as matching happens.
    new_collection_ids = set(collections_by_id.keys())

    # Match jwplayer videos to SMS collections
    for channel in channels:
        # Find an existing SMS collection id
        collection_id_prop = get_key_path(channel, 'custom.sms_collection_id')
        if collection_id_prop is None:
            n_skipped += 1
            continue

        # Retrieve the matching SMS collection (or record the inability to do so)
        try:
            collection = collections_by_id[
                int(parse_custom_prop('collection', collection_id_prop))
            ]
        except KeyError:
            unmatched_channels.append(channel)
            continue

        # Remove matched collection id from the new_collection_ids set
        new_collection_ids -= {collection.collection_id}

        # We now have a match between a channel and SMS collection. Record the match.
        associations.append((collection, channel))

    # Generate updates for existing channels
    for collection, channel in associations:
        updates.extend(update(collection, channel))

    # Generate creates for new channels
    for collection in (collections_by_id[collection_id] for collection_id in new_collection_ids):
        creates.extend(create(collection))

    LOG.info('Number of JWPlatform channels matched to SMS collections: %s',
             len(associations))
    LOG.info('Number of SMS collections with no existing channel: %s',
             len(new_collection_ids))
    LOG.info('Number of managed JWPlatform channels not matched to SMS collections: %s',
             len(unmatched_channels))
    LOG.info('Number of JWPlatform channels not managed by sms2jwplayer: %s', n_skipped)
    LOG.info('Number of channel creations: %s', len(creates))
    LOG.info('Number of channel updates: %s', len(updates))

    json.dump({'create': creates, 'update': updates}, fobj)


def process_channels(_, fobj, collections, channels):
    """
    Uses generic_channels_processor to generate a set of create/update jobs for the purpose of
    synchronising the title, description, & custom parameters of a set of JWPlayer channels with
    a set of SMS collections.

    """
    def create(collection):
        """Return a single job to create the JWPlatform channel resource."""
        return [{
            'type': 'channels',
            'resource': make_resource_for_channel(collection),
        }]

    def update(collection, channel):
        """Determine if any JWPlatform channel params differ from the matching SMS collection.
        If they do return a job to update these params."""

        expected_channel = make_resource_for_channel(collection)

        # Calculate delta from resource which exists to expected resource
        delta = updated_keys(channel, expected_channel)
        if len(delta) > 0:
            # The delta is non-empty, so construct an update request. FSR, the *update* request for
            # JWPlatform requires the channel be specified via 'channel_key' but said key appears
            # in the channel resource returned by /channels/list as 'key'.
            the_update = {'channel_key': channel['key']}
            the_update.update(delta)
            return [{
                'type': 'channels',
                'resource': the_update,
            }]
        return []

    generic_channels_processor(fobj, collections, channels, create, update)


def process_videos_in_channels(_, fobj, collections, channels):
    """
    Uses generic_channels_processor to generate a set of create/update jobs for the purpose of
    synchronising the videos contains by a set of JWPlayer channels with media items contains by
    a set of SMS collections.

    """
    def create(collection):
        """Return a set of videos_insert jobs for each media item in the collection"""
        return make_videos_in_channels_jobs(collection, 'videos_insert', collection.media_ids)

    def update(collection, channel):
        """Calculate the differences between the media_ids stored in the sms_media_ids channel
        param and collection.media_ids. Translate these differences into a set of
        videos_insert/videos_delete jobs (which is returned). """

        updates = []
        media_ids = []
        media_ids_prop = get_key_path(channel, 'custom.sms_media_ids')
        if media_ids_prop:
            media_ids = parse_custom_prop('media_ids', media_ids_prop).split(',')

        insert = set(collection.media_ids) - set(media_ids)
        if insert:
            updates.extend(make_videos_in_channels_jobs(collection, 'videos_insert', insert))

        delete = set(media_ids) - set(collection.media_ids)
        if delete:
            updates.extend(make_videos_in_channels_jobs(collection, 'videos_delete', delete))

    generic_channels_processor(fobj, collections, channels, create, update)


def make_videos_in_channels_jobs(collection, job_type, media_ids):
    """Helper to create the videos_insert|videos_delete jobs."""
    return [{
        'type': job_type,
        'resource': {'collection_id': collection.collection_id, 'media_id': int(media_id)}
    } for media_id in media_ids]


def process_videos(opts, fobj, items, videos):
    """
    Process video metadata records with reference to a list of media items.
    Write results to file as JSON document.

    """
    # Load items keyed by stripped path
    strip_from = int(opts['--strip-leading'])
    LOG.info('Stripping leading %s component(s) from filename', strip_from)

    # Statistics we record
    n_skipped = 0

    # The list of create and update jobs which need to be performed.
    creates, updates = [], []

    # A set of clip ids which already exist in JWPlatform
    existing_clip_ids = set()

    # A list of JWPlatform video resources which could not be matched to an SMS media object and
    # hence should be deleted.
    unmatched_videos = []

    # A list of (item, video resource) tuples representing that a given SMS media item is
    # represented by a JWPlatform video resource. This may be a one-to-many mapping; a single SMS
    # media item may have more than one JWPlatform video resource associated with it.
    associations = []

    # A dictionary which allows retrieving media items by clip id.
    items_by_clip_id = dict((item.clip_id, item) for item in items)

    # A dictionary, keyed by media id, of sequences of items associated with that media
    items_by_media_id = {}
    for item in items:
        media_items = items_by_media_id.get(item.media_id, list())
        media_items.append(item)
        items_by_media_id[item.media_id] = media_items

    # A set of item media_ids which could not be matched to a corresponding JWPlatform video. This
    # starts full of all items but items are removed as matching happens.
    new_media_ids = set(items_by_media_id.keys())

    # Match jwplayer videos to SMS items
    for video in videos:
        # Find an existing SMS clip id
        clip_id_prop = get_key_path(video, 'custom.sms_clip_id')
        if clip_id_prop is None:
            n_skipped += 1
            continue

        # Retrieve the matching SMS media item (or record the inability to do so)
        try:
            item = items_by_clip_id[int(parse_custom_prop('clip', clip_id_prop))]
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
        expected_video = make_resource_for_video(item)

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
            if item.image_md5:
                image_status = get_key_path(video, 'custom.sms_image_status')
                image_md5_changed = 'sms_image_md5' in delta.get('custom', {})
                # We want to trigger an upload of an image in the following circumstances:
                #   - The MD5s do not match *and* there is not an upload currently in progress
                md5_mismatch = image_md5_changed and image_status != 'image_status:loaded:'
                #   - The MD5s match but the matching upload was never attempted
                no_upload = not image_md5_changed and not image_status
                if md5_mismatch or no_upload:
                    # there is an SMS image and JWPlayer image MD5 either doesn't exist
                    # or doesn't match it - so we need to load the image
                    updates.append({
                        'type': 'image_load',
                        'resource': {
                            'video_key': video['key'], 'image_url': image_url(opts, item)
                        },
                    })

        if item.image_md5 and video['custom'].get('sms_image_status') == 'image_status:loaded:':
            # there is an SMS image and the image has been loaded but needs to be checked
            updates.append({'type': 'image_check', 'resource': {'video_key': video['key']}})

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

        video = make_resource_for_video(item)
        video.update({
            'download_url': url(opts, item),
        })
        creates.append({
            'type': 'videos',
            'resource': video,
        })

    LOG.info('Number of JWPlatform videos matched to SMS media items: %s', len(associations))
    LOG.info('Number of SMS media items with no existing video: %s', len(new_media_ids))
    LOG.info('Number of managed JWPlatform videos not matched to SMS media items: %s',
             len(unmatched_videos))
    LOG.info('Number of JWPlatform videos not managed by sms2jwplayer: %s', n_skipped)
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
            delta[key] = value
        else:
            # Key is in source
            if isinstance(value, dict):
                # Value is itself a dict so recurse
                sub_delta = updated_keys(source_value, value)
                if len(sub_delta) > 0:
                    delta[key] = sub_delta
            elif value != source_value:
                # Value differs between source and target. Return delta.
                delta[key] = value

    return delta


def make_resource_for_video(item):
    """
    Construct what the JWPlatform video resource for a SMS media item should look like.

    """

    # Start making the video resource. We cuddle the id numbers in <type>:...: so that we can
    # search for "exactly" the media id or clip id rather than simply a video whose id contains
    # another.
    custom_props = {
        'sms_media_id': 'media:{}:'.format(item.media_id),
        'sms_clip_id': 'clip:{}:'.format(item.clip_id),
        # format - migration not required (used to determine which clip to use)
        # filename - migration not required (used to determine the download URL)
        'sms_created_at': 'created_at:{}:'.format(item.created_at.isoformat()),
        # title - migrated as media item title
        # description - migrated as media item description
        'sms_collection_id': 'collection:{}:'.format(item.collection_id),
        'sms_instid': 'instid:{}:'.format(item.instid),
        'sms_aspect_ratio': 'aspect_ratio:{}:'.format(item.aspect_ratio),
        'sms_created_by': 'created_by:{}:'.format(item.creator),
        'sms_publisher': 'publisher:{}:'.format(item.publisher),
        'sms_copyright': 'copyright:{}:'.format(item.copyright),
        'sms_language': 'language:{}:'.format(item.language),
        'sms_keywords': 'keywords:{}:'.format(item.keywords),
        # visibility - migration merged with sms_acl
        'sms_acl': 'acl:{}:'.format(convert_acl(item.visibility, item.acl)),
        'sms_screencast': 'screencast:{}:'.format(item.screencast),
        'sms_image_id': 'image_id:{}:'.format(item.image_id),
        'sms_image_md5': 'image_md5:{}:'.format(item.image_md5),
        'sms_featured': 'featured:{}:'.format(item.featured),
        'sms_branding': 'branding:{}:'.format(item.branding),
        'sms_last_updated_at': 'last_updated_at:{}:'.format(item.last_updated_at),
        'sms_updated_by': 'updated_by:{}:'.format(item.updated_by),
        'sms_downloadable': 'downloadable:{}:'.format(item.downloadable),
        'sms_withdrawn': 'withdrawn:{}:'.format(item.withdrawn),
    }

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


def make_resource_for_channel(collection):
    """
    Construct what the JWPlatform channel resource for a SMS collection should look like.

    """
    # Start making the channel resource. We cuddle the id numbers in <type>:...: so that we can
    # search for "exactly" the collection id rather than simply a channel whose id contains
    # another.
    resource = {
        "custom": {
            'sms_collection_id': 'collection:{}:'.format(collection.collection_id),
            'sms_website_url': 'website_url:{}:'.format(collection.website_url),
            'sms_created_by': 'created_by:{}:'.format(collection.created_by),
            'sms_instid': 'instid:{}:'.format(collection.instid),
            'sms_groupid': 'groupid:{}:'.format(collection.groupid),
            'sms_image_id': 'image:{}:'.format(collection.image_id),
            'sms_acl': 'acl:{}:'.format(collection.acl),
            'sms_created_at': 'created_at:{}:'.format(collection.created_at.isoformat()),
            'sms_last_updated_at': 'last_updated_at:{}:'.format(
                collection.last_updated_at.isoformat()
            ),
            'sms_updated_by': 'updated_by:{}:'.format(collection.updated_by),
        },
    }

    # Add title and description if present
    for key, value in (('title', collection.title), ('description', collection.description)):
        value = sanitise(value)
        if value.strip() != '':
            resource[key] = value

    return resource


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
    return urllib.parse.urljoin(opts['--base-image-url'], str(item.image_id))


def sanitise(s, max_length=4096):
    """
    Strip odd characters from a string and sanitise the length to avoid JWPlatform complaining.

    """
    # Map control characters to empty string
    s = s.translate(dict.fromkeys(range(32)))

    # Truncate
    s = s[:max_length]
    return s
