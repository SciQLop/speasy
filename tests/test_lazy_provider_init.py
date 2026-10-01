import os
import subprocess
import sys
import textwrap
import unittest


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


if __name__ == "__main__":
    unittest.main()
