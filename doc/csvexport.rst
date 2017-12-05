CSV Export Format
=================

The :download:`dump_sms_csv_files.sh <../scripts/dump_sms_csv_files.sh>` script
can be run on the SMS hosting box to dump an export of the current state of the
SMS to a CSV file which can be ingested by this tool. The CSV consists of a
single header line and then rows of data. The CSV columns are as follows:

media_id
    Numeric ID for the SMS media item. An SMS media item may have multiple
    clips associated with it which are encoded into various formats. The media
    item is the fundamental object.
clip_id
    Numeric ID for the SMS clip item. There may be multiple clips associated
    with a single media item but they must have a unique format.
format
    One of ``audio`` or ``archive-h264`` depending on whether the clip is
    audio-only or video and audio.
filename
    The filename on the SMS hosting machine where the video/audio file is
    located.
created_at
    An ISO 8601 formatted date and time indicating when the media item was first
    created.
title
    A string giving the title of the media item
description
    A string giving the description of the media item

