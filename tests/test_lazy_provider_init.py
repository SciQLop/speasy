import os
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

import speasy as spz
from speasy.core.requests_scheduling import request_dispatch as rd


def _run(script, disabled=""):
    env = {**os.environ, "SPEASY_SKIP_INIT_PROVIDERS": "1", "SPEASY_CORE_DISABLED_PROVIDERS": disabled}
    return subprocess.run([sys.executable, "-c", textwrap.dedent(script)], env=env,
                          capture_output=True, text=True, timeout=600)


class LazyProviderInit(unittest.TestCase):
    def test_providers_initialize_on_first_use(self):
        result = _run("""
            import speasy as spz
            from speasy.core.requests_scheduling.request_dispatch import PROVIDERS
            assert PROVIDERS == {}, PROVIDERS
            assert spz.inventories.tree.ssc.Trajectories.wind is not None
            assert set(PROVIDERS) == {"ssc", "sscweb"}, PROVIDERS
            assert spz.ssc is PROVIDERS["ssc"]
            assert spz.get_data("amda/imf", "2016-10-10", "2016-10-10T01") is not None
            assert "amda" in PROVIDERS and "cda" not in PROVIDERS, PROVIDERS
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_disabled_provider_stays_none(self):
        result = _run("""
            import speasy as spz
            from speasy.core.requests_scheduling.request_dispatch import PROVIDERS
            assert spz.amda is None
            assert not hasattr(spz.inventories.tree, "amda")
            assert PROVIDERS == {}, PROVIDERS
        """, disabled="amda")
        self.assertEqual(result.returncode, 0, result.stderr)


class EnsureProvider(unittest.TestCase):
    # In-process counterpart of the subprocess tests above, the provider init itself is mocked
    def setUp(self):
        self._saved_cda = rd.__dict__.pop("cda", None)
        self._saved_tree = spz.inventories.tree.__dict__.pop("cda", None)

    def tearDown(self):
        rd.__dict__["cda"] = self._saved_cda
        if self._saved_tree is not None:
            spz.inventories.tree.__dict__["cda"] = self._saved_tree

    def test_alias_initializes_main_provider_once(self):
        init = Mock()
        with patch.dict(rd._INITIALIZERS, {"cda": init}):
            rd._ensure_provider("cdaweb")
            self.assertIsNone(rd.cda)
            rd._ensure_provider("cda")
        init.assert_called_once_with()

    def test_inventory_tree_initializes_provider(self):
        inventory = object()
        init = Mock(side_effect=lambda: spz.inventories.tree.__dict__.__setitem__("cda", inventory))
        with patch.dict(rd._INITIALIZERS, {"cda": init}):
            self.assertIs(spz.inventories.tree.cda, inventory)
            with self.assertRaises(AttributeError):
                spz.inventories.tree._private
        init.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
