"""
The tidy subcommand will examine the JWPlatform metadata and generate an update job which can be
applied via applyupdatejob. This update job will "tidy" the JWPlatform database in the following
ways:

- Each media id will have exactly one video associated with it with preference given to ones of
  type "video". Other videos will be deleted.

"""
import json
import logging

from . import util


LOG = logging.getLogger(__name__)


def main(opts):
    videos = []
    for metadata_fn in opts['<metadata>']:
        with open(metadata_fn) as f:
            videos.extend(json.load(f).get('videos', []))
    LOG.info('Loaded metadata for %s videos', len(videos))

    with util.output_stream(opts) as fobj:
        process_videos(opts, fobj, videos)


def process_videos(opts, fobj, videos):
    """
    Process videos and write update job to fobj.

    """
    # Delete jobs
    deletes = []

    # Group videos by media id
    videos_by_media_id = {}
    n_grouped = 0
    for video in videos:
        media_id_prop = util.get_key_path(video, 'custom.sms_media_id')
        if media_id_prop is None:
            continue

        try:
            media_id = int(util.parse_custom_prop('media', media_id_prop))
        except ValueError:
            LOG.error('Could not parse media id prop: %s', media_id_prop)
        else:
            group = videos_by_media_id.get(media_id, [])
            group.append(video)
            videos_by_media_id[media_id] = group
            n_grouped += 1

    LOG.info('Grouped %s videos by media id into %s groups', n_grouped, len(videos_by_media_id))
    LOG.info('Videos without media id: %s', len(videos) - n_grouped)

    for media_id, group in videos_by_media_id.items():
        video_keys = set(video['key'] for video in group)
        blessed_key = None

        # Attempt to find a video clip first
        for video in group:
            if video['mediatype'] == 'video':
                blessed_key = video['key']
                break

        # If failed, find an audio clip
        if blessed_key is None:
            for video in group:
                if video['mediatype'] == 'audio':
                    blessed_key = video['key']
                    break

        if blessed_key is None:
            LOG.warning('Could not find video or audio media for media id %s', media_id)
            continue

        # Remove the blessed key from the video keys, the rest should be deleted
        video_keys.remove(blessed_key)
        for key in video_keys:
            deletes.append({'type': 'videos', 'resource': {'video_key': key}})

    LOG.info('Number of delete jobs: %s', len(deletes))
    json.dump({'delete': deletes}, fobj)
