from unittest import mock

from io import StringIO

from sms2jwplayer.util import upload_thumbnail_from_url, channel_for_collection_id

from .util import JWPlatformTestCase

CHANNEL_FIXTURE = {
    'key': 'MrtH04gm',
    'title': 'Light, Clocks and Sleep',
    'description': 'The Discovery of a New Photoreceptor within the Eye',
    'custom': {
        'sms_collection_id': 'collection:123:'
    }
}


class UtilTests(JWPlatformTestCase):

    def test_upload_thumbnail_from_url(self):
        """Tests a successful call of upload_thumbnail_from_url()"""

        # setup

        query = {
            'key': '3Kgs63f3',
            'token': 'e2bbad0fd889d5d2e30047596cfe3789778257d2',
        }

        self.client.videos.thumbnails.update.return_value = {
            'link': {
                'protocol': 'http',
                'address': 'upload.jwplatform.com',
                'path': '/v1/videos/upload',
                'query': query
            }
        }

        urlopen = self.patch_and_start('urllib.request.urlopen')
        urlopen.return_value = StringIO("image")

        requests_post = self.patch_and_start('requests.post')
        requests_post.return_value = mock.Mock()
        requests_post.return_value.json.return_value = {"status": "ok"}

        # test

        response = upload_thumbnail_from_url(
            '3Kgs63f3', 'https://sms.cam.ac.uk/image/1393664', client=self.client
        )

        # check

        self.assertEquals(response, {'status': 'ok'})

        self.client.videos.thumbnails.update.assert_called_with(video_key='3Kgs63f3')

        urlopen.assert_called_with('https://sms.cam.ac.uk/image/1393664')

        requests_post.assert_called_with(
            'http://upload.jwplatform.com/v1/videos/upload',
            params=query,
            files={'file': urlopen.return_value}
        )

    def test_channel_for_collection_id__success(self):
        """Test that a channel is found"""

        self.client.channels.list.return_value = {
            'status': 'ok',
            'channels': [CHANNEL_FIXTURE]
        }

        channel = channel_for_collection_id(123, client=self.client)

        self.assertEquals(channel, CHANNEL_FIXTURE)

        self.client.channels.list.assert_called_with(**{
            'search:custom.sms_collection_id': 'collection:123:',
        })

    def test_channel_for_collection_id__no_channel(self):
        """Test that no channel is found"""

        self.client.channels.list.return_value = {
            'status': 'ok',
            'channels': []
        }

        self.assertIsNone(channel_for_collection_id(123, client=self.client))

    def test_channel_for_collection_id__2_channels(self):
        """Test that if 2 channels are found - one is returned and a warning is logged"""

        self.client.channels.list.return_value = {
            'status': 'ok',
            'channels': [
                CHANNEL_FIXTURE,
                {**CHANNEL_FIXTURE, **{'key': 'JvqGHkJR'}}
            ]
        }

        with self.assertLogs() as logs:
            channel = channel_for_collection_id(123, client=self.client)
            self.assertEqual(logs.output, [
                'WARNING:sms2jwplayer.util:Collection 123 matches more than one channel'
            ])

        self.assertEquals(channel, CHANNEL_FIXTURE)
