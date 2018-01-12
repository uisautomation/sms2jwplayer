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
    'MediaItem',
    'media_id clip_id format filename created_at title description collection_id instid'
)
MediaItem.__doc__ = """
Representation of a single media item within the SMS.

.. seealso:: :any:`csvexport`
"""


# Callables which massage strings into the right types for each column
_MEDIA_ITEM_TYPES = [
    int, int, MediaFormat, str, dateutil.parser.parse, str, str, int, str
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
        MediaItem._make([t(v) for t, v in zip(_MEDIA_ITEM_TYPES, row[:9])])
        for row in reader
    ]
