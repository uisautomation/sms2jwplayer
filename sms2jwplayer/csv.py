"""
Parsing SMS export CSV format.

"""
import collections
import csv
import enum

import dateutil.parser


CollectionItem = collections.namedtuple('CollectionItem', (
    'collection_id', 'title', 'description',
    'website_url', 'created_by', 'instid',
    'groupid', 'image_id', 'acl',
    'created_at', 'last_updated_at', 'updated_by',
    'media_ids'
))

CollectionItem.__doc__ = """
Representation of a single collection within the SMS.
The attributes below are all the columns in the :any:`csvexport`. Unless otherwise stated, the
attribute is migrated to a custom property in jwplayer and the name of that property will be the
same but prefixed by "`sms_`".

* ``collection_id`` - Numeric ID for the SMS collection.

* ``title`` - A string giving the title of the collection. This is migrated directly to the title
  of the channel in jwplayer and not as a custom property.

* ``description`` - A string giving the description of the collection. This is migrated directly to
  the description of the channel in jwplayer and not as a custom property.

* ``website_url`` - An optional link to the users website.

* ``created_by`` - The media item's creator.

* ``instid`` - String ID for institution which owns the collection.

* ``groupid - The ID of a lookup group whose members can edit this collection.

* ``image_id`` - The id of the collection's custom thumbnail - empty if a thumbnail was never
  uploaded to legacy SMS.

* ``acl`` - An ACL defining the visibility of the collection.

* ``created_at`` - An ISO 8601 formatted date and time indicating when the collection was first
  created.

* ``last_updated_at`` - When the collection was last updated.

* ``updated_by`` - Who last updated the collection (CRSID).

* ``media_ids`` - A CSV list of the ids all the media items contained by this collection.
"""

# Callables which massage strings into the right types for each column
CollectionItem._ITEM_TYPES = [
    int, str, str,
    str, str, str,
    str, lambda i: int(i) if i != '' else None, lambda acl: acl.split(','),
    dateutil.parser.parse, dateutil.parser.parse, str,
    lambda media_ids: media_ids.split(',') if media_ids != '' else [],
]


class MediaFormat(enum.Enum):
    VIDEO = 'archive-h264'
    AUDIO = 'audio'
    AAC = 'aac'
    AIFF = 'aiff'
    FLV = 'flv'
    IPOD = 'ipod'
    MOV = 'mov'
    MP3 = 'mp3'
    MPEG4 = 'mpeg4'
    RA = 'ra'
    RM = 'rm'
    WEBM = 'webm'
    WMV = 'wmv'


class MediaQuality(enum.Enum):
    LOW_RES = '360p'
    HIGH_RES = '720p'
    HIGH = 'high'
    LOW = 'low'
    MEDIUM = 'medium'


MediaItem = collections.namedtuple(
    'MediaItem', ('media_id clip_id format filename created_at '
                  'title description collection_id instid aspect_ratio '
                  'creator publisher copyright language keywords visibility '
                  'acl screencast image_id image_md5 '
                  'featured branding last_updated_at updated_by '
                  'downloadable withdrawn quality')
)
MediaItem.__doc__ = """
Representation of a single media item within the SMS.
The attributes below are all the columns in the :any:`csvexport`. Unless otherwise stated, the
attribute is migrated to a custom property in jwplayer and the name of that property will be the
same but prefixed by "`sms_`".

* ``media_id`` - Numeric ID for the SMS media item. An SMS media item may have multiple clips
  associated with it which are encoded into various formats. The media item is the fundamental
  object.

* ``clip_id`` - Numeric ID for the SMS clip item. There may be multiple clips associated with a
  single media item but they must have a unique format.

* ``format`` - One of ``audio`` or ``archive-h264`` depending on whether the clip is audio-only or
  video and audio. This isn't migrated as it is irrelevant in the context of jwplayer.

* ``filename`` - The filename on the SMS hosting machine where the video/audio file is located.
  This isn't migrated as it is irrelevant in the context of jwplayer.

* ``created_at`` - An ISO 8601 formatted date and time indicating when the media item was first
  created.

* ``title`` - A string giving the title of the media item. This is migrated directly to the title
  of the media item in jwplayer and not as a custom property.

* ``description`` - A string giving the description of the media item. This is migrated directly to
  the description of the media item in jwplayer and not as a custom property.

* ``collection_id`` - Numeric ID for the SMS collection.

* ``instid`` - String ID for institution which owns the collection.

* ``aspect_ratio`` - The media item's aspect ratio.

* ``creator`` - The media item's creator. The migrated custom property name in sms_created_at.

* ``publisher`` - The publisher of the media item.

* ``copyright`` - The copyright of the media item.

* ``language`` - The code of the language relevant to the media item.

* ``keywords`` - List of keywords relevant to the media item for the purposes of search.

* ``visibility`` - The visibility of the media item. This isn't migrated as it has been merged with
  ``acl`` in a more logical scheme. Can be any one of the following values
    * ``world``          - world visible (ignored if ACL is defined)
    * ``cam``            - cambridge visible (ignored if ACL is defined)
    * ``world-overrule`` - world visible (any ACL is ignored)
    * ``cam-overrule``   - cambridge visible (any ACL is ignored)
    * ``acl-overrule``   - visibility is defined by the ACL

* ``acl`` - A comma seperated list of any of: INSTIDs, CRSIDs, or lookup groups (an integer).
  Defines who can see the media item unless ``visibility`` is world-overrule or cam-overrule.
  ``acl`` and ``visibility`` are combined when migrating to ``sms_acl`` in a new scheme as a comma
  seperated list. At the risk of stating the obvious, the list is OR'd to produce the access list.
  Each ``ace`` can by of any of the following values
    * ``WORLD``         - world visible
    * ``CAM``           - cambridge visible
    * ``INST_instid``   - visible to an institution
    * ``GROUP_groupid`` - visible to a group (groupid can by either numeric id or name)
    * ``USER_crsid``    - visible to an individual

* ``screencast`` - Whether or not the media item is a screencast.

* ``image_id`` - The id of the media item's custom thumbnail - empty if a thumbnail was never
  uploaded to legacy SMS.

* ``image_md5`` - The md5 of the media item's custom thumbnail - empty if a thumbnail was never
  uploaded to legacy SMS.

* ``featured`` - Whether or not the media item is featured on the frontpage.

* ``branding`` - No definition available.

* ``last_updated_at`` - When the media item was last updated.

* ``updated_by`` - Who last updated the media item (CRSID).

* ``downloadable`` - Whether or not the media item can be downloaded from it's page.

* ``withdrawn`` - No definition available.

* ``quality`` - The quality of the encoded video. E.g. "high", "720p".
"""

# Callables which massage strings into the right types for each column
MediaItem._ITEM_TYPES = [
    int, int, MediaFormat, str, dateutil.parser.parse,
    str, str, int, str, str,
    str, str, str, str, str, str,
    lambda acl: acl.split(','), lambda b: b == 't', lambda i: int(i) if i != '' else None, str,
    lambda b: b == 't', lambda b: b == 't', dateutil.parser.parse, str,
    lambda b: b == 't', str, MediaQuality
]


def load(item_type, fobj, skip_header_row=True):
    """Load an SMS export from a file object. Return a list of item_type instances.
    If *skip_header_row* is ``True``, the first line of the CSV file is ignored.

    The CSV file must be in the format described in :any:`csvexport`.
    Any extra columns are ignored.
    The columns are converted by the type defined in item_type._ITEM_TYPES.

    """
    reader = csv.reader(fobj)

    # Skip header if required
    if skip_header_row:
        next(reader)

    return [
        item_type._make([t(v) for t, v in zip(item_type._ITEM_TYPES, row)])
        for row in reader
    ]
