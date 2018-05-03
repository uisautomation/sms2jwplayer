from unittest import mock

from io import StringIO

from sms2jwplayer.util import upload_thumbnail_from_url

from .util import JWPlatformTestCase


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
        requests_post.return_value.text = '{"status": "ok"}'

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
