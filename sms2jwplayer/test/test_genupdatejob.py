import logging
import unittest

from sms2jwplayer.genupdatejob import convert_acl

LOG = logging.getLogger(__name__)


class ConvertAclTests(unittest.TestCase):
    """All tests for :py:`~genupdatejob.convert_acl`"""

    def test_null_acls(self):
        """Check in particular that [''] is treated as a null ACL"""

        # null ACLs
        self.assertEqual(convert_acl('world', None), 'WORLD')
        self.assertEqual(convert_acl('world', ''), 'WORLD')
        self.assertEqual(convert_acl('world', []), 'WORLD')
        self.assertEqual(convert_acl('world', ['']), 'WORLD')

        # non-null ACL
        self.assertEqual(convert_acl('world', ['102592']), 'GROUP_102592')

    def test_visibility_acl_combinations(self):
        """
        Test conversion for all combinations (found in PROD data) of media item visibility and acl
        """

        # check that INST, GROUP, & USER ACE's convert
        self.assertEqual(
            convert_acl('acl-overrule', ['001705', 'UIS', 'mjd66', 'aj333']),
            'GROUP_001705,INST_UIS,USER_mjd66,USER_aj333'
        )

        # check that 'cam' is overridden by ACL
        self.assertEqual(
            convert_acl('cam', ['001705', 'UIS']),
            'GROUP_001705,INST_UIS'
        )

        # check that 'cam' is converted when no ACL
        self.assertEqual(
            convert_acl('cam', ['']),
            'CAM'
        )

        # check that 'cam-overrule' is converted
        self.assertEqual(
            convert_acl('cam-overrule', ['']),
            'CAM'
        )

        # check that 'cam-overrule' is converted regardless of ACL
        self.assertEqual(
            convert_acl('cam-overrule', ['si202', 'jrn30']),
            'CAM,USER_si202,USER_jrn30'
        )

        # check that 'world' is overridden by ACL
        self.assertEqual(
            convert_acl('world', ['101128', 'jew46', 'mec22']),
            'GROUP_101128,USER_jew46,USER_mec22'
        )

        # check that 'world' is converted when no ACL
        self.assertEqual(
            convert_acl('world', ['']),
            'WORLD'
        )

        # check that 'world-overrule' is converted
        self.assertEqual(
            convert_acl('world-overrule', ['']),
            'WORLD'
        )

        # check that 'world-overrule' is converted regardless of ACL
        self.assertEqual(convert_acl(
            'world-overrule', ['jar35', 'lmd11', 'hs243']),
            'WORLD,USER_jar35,USER_lmd11,USER_hs243'
        )
