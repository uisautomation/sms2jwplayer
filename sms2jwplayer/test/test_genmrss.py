import logging
import os
import pprint
import tempfile
import unittest
import unittest.mock as mock

import feedparser

from sms2jwplayer import main
from sms2jwplayer.test.io import data_path, captured_stdout


LOG = logging.getLogger(__name__)


class BasicCallTest(unittest.TestCase):
    """
    Test basic calls to genmrss.

    """
    def test_basic_call(self):
        """Calling genmrss with example csv does not throw."""
        genmrss('--base=http://example.com/', data_path('export_example.csv'))

    def test_file_output(self):
        """
        Calling genmrss with example csv and output file writes output to csv
        file.

        """
        with tempfile.TemporaryDirectory() as td:
            csv_out = os.path.join(td, 'out.csv')
            genmrss(
                '--base=http://example.com/', data_path('export_example.csv'),
                csv_out
            )

            # Check some output was written
            with open(csv_out) as f:
                self.assertGreater(len(f.read()), 0)

    def test_stdout(self):
        """
        Calling genmrss with example csv and no output file writes output to
        standard output.

        """
        with captured_stdout() as stdout:
            genmrss(
                '--base=http://example.com/', data_path('export_example.csv')
            )

        # Check some output was written
        self.assertGreater(len(stdout.getvalue()), 0)


class MRSSFormatTests(unittest.TestCase):
    """Test format of feed returned by genmrss."""
    BASE_URL = 'http://example.com/base/'

    def setUp(self):
        with captured_stdout() as stdout:
            genmrss(
                '--base=' + self.BASE_URL, data_path('export_example.csv')
            )

        # Store raw and parsed output
        self.output_str = stdout.getvalue()
        self.feed = feedparser.parse(self.output_str)

        # Print the output
        for line in self.output_str.splitlines():
            LOG.info('Output: %s', line.strip('\n'))

        # Pretty-print the parsed feed
        for line in pprint.pformat(self.feed).splitlines():
            LOG.info('Feed: %s', line.strip('\n'))

    def test_entry_count(self):
        """The right number of items are present."""
        self.assertEqual(len(self.feed.entries), 2)

    def test_entries_have_urls(self):
        """Entries have media URLs set."""
        for entry in self.feed.entries:
            media_content = entry['media_content']
            self.assertEqual(len(media_content), 1)
            url = media_content[0]['url']
            self.assertTrue(url.startswith(self.BASE_URL))

    def test_first_entry_title(self):
        """First entry has correct title."""
        self.assertEqual(self.feed.entries[0]['title'], 'foo')

    def test_first_entry_description(self):
        """First entry has correct description."""
        self.assertEqual(self.feed.entries[0]['description'], 'foobar')


def genmrss(*args):
    """Call the genmrss command as if from command line."""
    argv = ['sms2jwplayer', 'genmrss']
    argv.extend(args)
    LOG.info('calling with argv: %r', argv)
    with mock.patch('sys.argv', argv):
        main()
