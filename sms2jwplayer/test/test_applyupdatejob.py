import json
import logging
import os
import tempfile
import unittest.mock as mock

from sms2jwplayer import main

from .util import JWPlatformTestCase

LOG = logging.getLogger(__name__)


class ApplyUpdateJobTests(JWPlatformTestCase):
    """
    Test applyupdatejob functionality

    """
    def setUp(self):
        super().setUp()
        credentials = {'JWPLAYER_API_KEY': 'xxx', 'JWPLAYER_API_SECRET': 'yyy'}
        self.environ_patcher = mock.patch('os.environ', credentials)
        self.environ_patcher.start()

    def tearDown(self):
        self.environ_patcher.stop()
        super().tearDown()

    def test_basic_call(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            jobfile = os.path.join(tmp_dir, 'job.json')
            with open(jobfile, 'w') as f:
                json.dump({
                    'updates': [
                        {'key': 'abc', 'custom': {'one': 1}},
                        {'key': 'def', 'custom': {'foo': 'bar', 'buzz': 3}},
                    ]
                }, f)
            applyupdatejob(jobfile)

        self.client.videos.update.assert_has_calls([
            mock.call(**{'video_key': 'abc', 'custom.one': '1'}),
            mock.call(**{'video_key': 'def', 'custom.foo': 'bar', 'custom.buzz': '3'}),
        ], any_order=True)


def applyupdatejob(*args):
    """Call the applyupdatejob command as if from command line."""
    argv = ['sms2jwplayer', 'applyupdatejob']
    argv.extend(args)
    LOG.info('calling with argv: %r', argv)
    with mock.patch('sys.argv', argv):
        main()
