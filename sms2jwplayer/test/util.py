import unittest
import unittest.mock as mock


class JWPlatformTestCase(unittest.TestCase):
    """
    A test case which patches the jwplatform.Client object.

    """
    def setUp(self):
        client_callable = self.patch_and_start('jwplatform.Client')
        self.client = mock.MagicMock()
        client_callable.return_value = self.client

    def patch_and_start(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()
