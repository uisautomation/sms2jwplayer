CSV Export
==========

The :download:`export_sms_csv.sh <../scripts/export_sms_csv.sh>` script will SSH into a SMS
hosting box to dump an export of the current state of the SMS to a CSV file which is then ingested
by this tool. The CSV consists of a single header line and then rows of data. The CSV columns are
not defined here -  rather they are defined on the ``MediaItem`` in the :any:`reference`.

Example
-------

Here is an example file formatted correctly as used in the test suite:

.. literalinclude:: ../sms2jwplayer/test/data/export_example.csv
    :language: csv
