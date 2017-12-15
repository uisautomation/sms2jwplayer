import unittest
import unittest.mock as mock


class JWPlatformTestCase(unittest.TestCase):
    """
    A test case which patches the jwplatform.Client object.

    """
    def setUp(self):
        self.jwclient_patcher = mock.patch('jwplatform.Client')
        self.client_callable = self.jwclient_patcher.start()
        self.client = mock.MagicMock()
        self.client_callable.return_value = self.client

    def tearDown(self):
        self.jwclient_patcher.stop()
