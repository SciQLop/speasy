import unittest

import speasy as spz


class VirtualProviderRegistration(unittest.TestCase):
    def test_virtual_provider_is_registered(self):
        self.assertIn("virtual", spz.list_providers())


if __name__ == '__main__':
    unittest.main()
