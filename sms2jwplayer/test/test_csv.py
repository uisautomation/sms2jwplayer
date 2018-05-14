import datetime
from unittest import TestCase

from sms2jwplayer import csv as smscsv
from sms2jwplayer.csv import MediaItem

from sms2jwplayer.test.io import open_data


class CSVLoadingTestCase(TestCase):
    def setUp(self):
        with open_data('export_example.csv') as f:
            self.items = smscsv.load(MediaItem, f)

    def test_item_count(self):
        """The correct number of items were loaded."""
        self.assertEqual(len(self.items), 2)

    def test_types(self):
        """Media items have the correct types for each field."""
        field_types = (
            ('clip_id', int), ('created_at', datetime.datetime),
            ('description', str), ('filename', str),
            ('format', smscsv.MediaFormat), ('media_id', int), ('title', str)
        )
        for item in self.items:
            for name, type_ in field_types:
                self.assertIsInstance(getattr(item, name), type_)
