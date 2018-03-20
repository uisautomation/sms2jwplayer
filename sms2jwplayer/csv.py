"""
Parsing SMS export CSV format.

"""
import collections
import csv
import enum

import dateutil.parser


class MediaFormat(enum.Enum):
    VIDEO = 'archive-h264'
    AUDIO = 'audio'


MediaItem = collections.namedtuple(
    'MediaItem', ('media_id clip_id format filename created_at '
                  'title description collection_id instid aspect_ratio '
                  'creator in_dspace publisher copyright language '
                  'keywords visibility acl screencast image_id '
                  'dspace_path featured branding last_updated_at updated_by '
                  'downloadable withdrawn abstract priority')
)
MediaItem.__doc__ = """
Representation of a single media item within the SMS. 
The attributes below are all the columns in the :any:`csvexport`. Unless otherwise stated, the 
attribute is migrated to a custom property in jwplayer and the name of that property will be the 
same but prefixed by "`sms_`".
"""
MediaItem.media_id.__doc__ = """
Numeric ID for the SMS media item. An SMS media item may have multiple clips 
associated with it which are encoded into various formats. The media item is the fundamental 
object.
"""
MediaItem.clip_id.__doc__ = """
Numeric ID for the SMS clip item. There may be multiple clips associated with a single media item 
but they must have a unique format.
"""
MediaItem.format.__doc__ = """
One of ``audio`` or ``archive-h264`` depending on whether the clip is audio-only or video and 
audio. This isn't migrated as it is irrelevant in the context of jwplayer.
"""
MediaItem.filename.__doc__ = """
The filename on the SMS hosting machine where the video/audio file is located.
This isn't migrated as it is irrelevant in the context of jwplayer.
"""
MediaItem.created_at.__doc__ = """
An ISO 8601 formatted date and time indicating when the media item was first created.
"""
MediaItem.title.__doc__ = """
A string giving the title of the media item. This is migrated directly to the title of the media 
item in jwplayer and not as a custom property.
"""
MediaItem.description.__doc__ = """
A string giving the description of the media item. This is migrated directly to the description of 
the media item in jwplayer and not as a custom property.
"""
MediaItem.collection_id.__doc__ = """
Numeric ID for the SMS collection.
"""
MediaItem.instid.__doc__ = """
String ID for institution which owns the collection.
"""
MediaItem.aspect_ratio.__doc__ = """
The media item's aspect ratio.
"""
MediaItem.creator.__doc__ = """
The media item's creator. The migrated custom property name in sms_created_at.
"""
MediaItem.in_dspace.__doc__ = """
Whether or not the media iten was archived in DSpace. This isn't migrated as it is irrelevant in 
the context of jwplayer.
"""
MediaItem.publisher.__doc__ = """
The publisher of the media item.
"""
MediaItem.copyright.__doc__ = """
The copyright of the media item.
"""
MediaItem.language.__doc__ = """
The code of the language relevant to the media item.
"""
MediaItem.keywords.__doc__ = """
List of keywords relevant to the media item for the purposes of search.
"""
MediaItem.visibility.__doc__ = """
The visibility of the media item. Can be any one of the following values:

    - ``world``          - world visible (ignored if ACL is defined)
    - ``cam``            - cambridge visible (ignored if ACL is defined)
    - ``world-overrule`` - world visible (any ACL is ignored)
    - ``cam-overrule``   - cambridge visible (any ACL is ignored)
    - ``acl-overrule``   - visibility is defined by the ACL
    
This isn't migrated as it has been merged with ``acl`` in a more logical scheme.
"""
MediaItem.acl.__doc__ = """
A comma seperated list of any of: INSTIDs, CRSIDs, or lookup groups (an integer). Defines who can 
see the media item unless ``visibility`` is world-overrule or cam-overrule. 

``acl`` and ``visibility`` are combined when migrating to ``sms_acl`` in a new scheme as a comma 
seperated list of any of the following values:

    - ``WORLD``         - world visible
    - ``CAM``           - cambridge visible
    - ``INST_instid``   - visible to an institution
    - ``GROUP_groupid`` - visible to a group (groupid can by either numeric id or name)
    - ``USER_crsid``    - visible to an individual
    
At the risk of stating the obvious, the list is OR'd to produce the access list.
"""
MediaItem.screencast.__doc__ = """
Whether or not the media item is a screencast.
"""
MediaItem.image_id.__doc__ = """
The id of the media item's thumbnail.
"""
MediaItem.dspace_path.__doc__ = """
The path of the media item archived in DSpace. This isn't migrated as it is irrelevant in the 
context of jwplayer.
"""
MediaItem.featured.__doc__ = """
Whether or not the media item is featured on the frontpage.
"""
MediaItem.branding.__doc__ = """
No definition available.
"""
MediaItem.last_updated_at.__doc__ = """
When the media item was last updated.
"""
MediaItem.updated_by.__doc__ = """
Who last updated the media item (CRSID).
"""
MediaItem.downloadable.__doc__ = """
Whether or not the media item can be downloaded from it's page.
"""
MediaItem.withdrawn.__doc__ = """
No definition available.
"""
MediaItem.abstract.__doc__ = """
A longer description of the media item. This isn't migrated as it's size makes this impractical.
"""
MediaItem.priority.__doc__ = """
A numeric priority (lowest = 0) that indicates how urgently a media item needs to be transcoded. 
This isn't migrated as it is irrelevant in the context of jwplayer.
"""

# Callables which massage strings into the right types for each column
_MEDIA_ITEM_TYPES = [
    int, int, MediaFormat, str, dateutil.parser.parse, str, str, int, str, str, str,
    lambda b: b == 't', str, str, str, str, str, lambda acl: acl.split(','), lambda b: b == 't',
    lambda i: int(i) if i != '' else None, str, lambda b: b == 't', lambda b: b == 't',
    dateutil.parser.parse, str, lambda b: b == 't', str, str, int
]


def load(fobj, skip_header_row=True):
    """Load an SMS export from a file object. Return a list of
    :py:class:`.MediaItem` instances. If *skip_header_row* is ``True``, the
    first line of the CSV file is ignored.

    The CSV file must be in the format described in :any:`csvexport`. Any extra
    columns are ignored. The ``media_id`` and ``clip_id`` columns are converted
    to integers and the ``created_at`` column is parsed into a
    :py:class:`datetime.datetime` instance.

    """
    reader = csv.reader(fobj)

    # Skip header if required
    if skip_header_row:
        next(reader)

    return [
        MediaItem._make([t(v) for t, v in zip(_MEDIA_ITEM_TYPES, row)])
        for row in reader
    ]


