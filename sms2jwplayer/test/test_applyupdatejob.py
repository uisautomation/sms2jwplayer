import json
import logging
import os
import tempfile
import unittest.mock as mock

from sms2jwplayer import main
from sms2jwplayer.applyupdatejob import resource_to_params

from .util import JWPlatformTestCase

LOG = logging.getLogger(__name__)


class ApplyUpdateJobTests(JWPlatformTestCase):
    """
    Test applyupdatejob functionality

    """
    def setUp(self):
        super().setUp()
        credentials = {'JWPLAYER_API_KEY': 'xxx', 'JWPLAYER_API_SECRET': 'yyy'}
        self.patch_and_start('os.environ', credentials)

    def test_basic_call(self):
        applyupdatejob({
            'update': [
                {'type': 'videos', 'resource': {'video_key': 'abc', 'custom': {'one': 1}}},
                {'type': 'videos', 'resource': {
                    'video_key': 'def', 'custom': {'foo': 'bar', 'buzz': 3}
                }},
            ]
        })

        self.client.videos.update.assert_has_calls([
            mock.call(**{'video_key': 'abc', 'custom.one': 1, 'http_method': 'POST'}),
            mock.call(**{'video_key': 'def', 'custom.foo': 'bar', 'custom.buzz': 3,
                         'http_method': 'POST'}),
        ], any_order=True)

    def test_image_load(self):
        upload_thumbnail_from_url = self.patch_and_start(
            'sms2jwplayer.util.upload_thumbnail_from_url'
        )
        upload_thumbnail_from_url.return_value = {'status': 'ok'}

        applyupdatejob({
            'update': [
                {'type': 'image_load', 'resource': {
                    'video_key': '3Kgs63f3', 'image_url': 'https://sms.cam.ac.uk/image/1393664'
                }}
            ]
        })

        upload_thumbnail_from_url.assert_called_with(
            client=self.client,
            image_url='https://sms.cam.ac.uk/image/1393664',
            video_key='3Kgs63f3',
        )

        self.client.videos.update.assert_called_with(
            http_method='POST', **{
                'video_key': '3Kgs63f3',
                'custom.sms_image_status': 'image_status:loaded:'
            }
        )

    def test_image_check(self):

        self.client.videos.thumbnails.show.return_value = {'thumbnail': {'status': 'ready'}}

        applyupdatejob(
            {'update': [{'type': 'image_check', 'resource': {'video_key': '3Kgs63f3'}}]}
        )

        self.client.videos.thumbnails.show(video_key='3Kgs63f3')

        self.client.videos.update.assert_called_with(
            http_method='POST', **{
                'video_key': '3Kgs63f3',
                'custom.sms_image_status': 'image_status:ready:'
            }
        )

    def test_resource_to_params(self):
        self.assertEquals(resource_to_params(
            {'a': {'x': 1, 'y': 2}, 'b': 3}), {'a.x': 1, 'a.y': 2, 'b': 3}
        )


def applyupdatejob(jobfile_content):
    """Call the applyupdatejob command as if from command line."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        jobfile = os.path.join(tmp_dir, 'job.json')
        with open(jobfile, 'w') as f:
            json.dump(jobfile_content, f)
        argv = ['sms2jwplayer', 'applyupdatejob', jobfile]
        LOG.info('calling with argv: %r', argv)
        with mock.patch('sys.argv', argv):
            main()
