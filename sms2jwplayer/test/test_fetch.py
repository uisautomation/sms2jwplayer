import logging
import unittest.mock as mock

from sms2jwplayer import main

from .util import JWPlatformTestCase

LOG = logging.getLogger(__name__)


class ExitException(Exception):
    pass


class CredentialTests(JWPlatformTestCase):
    """
    Test credentials are required

    """
    def test_no_credentials(self):
        """Calling fetch with no key or secret fails."""
        with mock.patch('sys.exit') as exit:
            with mock.patch('sys.exit') as exit:
                exit.side_effect = ExitException()
                with self.assertRaises(ExitException):
                    fetch()
        exit.assert_called_with(1)

    def test_no_secret(self):
        """Calling fetch with only key fails."""
        with mock.patch('os.environ', {'JWPLAYER_API_KEY': 'xxx'}):
            with mock.patch('sys.exit') as exit:
                exit.side_effect = ExitException()
                with self.assertRaises(ExitException):
                    fetch()
        exit.assert_called_with(1)

    def test_no_key(self):
        """Calling fetch with only secret fails."""
        with mock.patch('os.environ', {'JWPLAYER_API_SECRET': 'xxx'}):
            with mock.patch('sys.exit') as exit:
                exit.side_effect = ExitException()
                with self.assertRaises(ExitException):
                    fetch()
        exit.assert_called_with(1)


class FetchTests(JWPlatformTestCase):
    """
    Test fetch functionality

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
        self.client.videos.list.return_value = {
            'videos': [], 'total': 0, 'offset': 0, 'limit': 0
        }
        fetch()


def fetch(*args):
    """Call the fetch command as if from command line."""
    argv = ['sms2jwplayer', 'fetch']
    argv.extend(args)
    LOG.info('calling with argv: %r', argv)
    with mock.patch('sys.argv', argv):
        main()
