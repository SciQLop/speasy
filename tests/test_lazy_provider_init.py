import os
import subprocess
import sys
import textwrap
import threading
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

    def test_provider_names_are_listed_without_initializing(self):
        result = _run("""
            import speasy as spz
            from speasy.core.requests_scheduling.request_dispatch import PROVIDERS
            assert {"amda", "cda", "ssc"} <= set(dir(spz)), dir(spz)
            for namespace in (spz.inventories.tree, spz.inventories.flat_inventories):
                assert {"cda", "ssc", "archive"} <= set(dir(namespace)), dir(namespace)
                assert "amda" not in dir(namespace), dir(namespace)
            assert PROVIDERS == {}, PROVIDERS
        """, disabled="amda")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_flat_inventory_file_alias_initializes_archive(self):
        result = _run("""
            import speasy as spz
            from speasy.core.requests_scheduling.request_dispatch import PROVIDERS
            assert spz.inventories.flat_inventories.file is spz.inventories.flat_inventories.archive
            assert set(PROVIDERS) == {"archive", "generic_archive"}, PROVIDERS
        """)
        self.assertEqual(result.returncode, 0, result.stderr)


class EnsureProvider(unittest.TestCase):
    # In-process counterpart of the subprocess tests above, the provider class itself is faked
    def setUp(self):
        for namespace in (rd.__dict__, rd.PROVIDERS, spz.inventories.tree.__dict__):
            patcher = patch.dict(namespace)
            patcher.start()
            self.addCleanup(patcher.stop)
        rd.__dict__.pop("cda", None)
        rd.PROVIDERS.clear()
        spz.inventories.tree.__dict__.pop("cda", None)

    def test_alias_initializes_main_provider_once(self):
        provider_class = Mock(spec=[])
        with patch.dict(rd._PROVIDERS_SPEC, {"cda": (provider_class, ("cdaweb",))}):
            first = rd._ensure_provider("cdaweb")
            self.assertIs(rd.cda, first)
            self.assertIs(rd._ensure_provider("cda"), first)
        provider_class.assert_called_once_with()

    def test_inventory_tree_initializes_provider(self):
        inventory = object()
        provider_class = Mock(spec=[], side_effect=lambda: spz.inventories.tree.__dict__.__setitem__("cda", inventory))
        with patch.dict(rd._PROVIDERS_SPEC, {"cda": (provider_class, ())}):
            self.assertIs(spz.inventories.tree.cda, inventory)
            with self.assertRaises(AttributeError):
                spz.inventories.tree._private
        provider_class.assert_called_once_with()

    def test_concurrent_first_use_waits_for_init(self):
        started, release = threading.Event(), threading.Event()

        class SlowProvider:
            def __init__(self):
                started.set()
                release.wait(10)

        results = {}

        def first_use(key):
            results[key] = rd._ensure_provider("cda")

        with patch.dict(rd._PROVIDERS_SPEC, {"cda": (SlowProvider, ())}):
            first = threading.Thread(target=first_use, args=("first",))
            first.start()
            started.wait(10)
            second = threading.Thread(target=first_use, args=("second",))
            second.start()
            second.join(0.2)
            release.set()
            first.join(10)
            second.join(10)
        self.assertIsInstance(results["first"], SlowProvider)
        self.assertIs(results["second"], results["first"])

    def test_initialized_provider_does_not_wait_for_another_init(self):
        provider, lock_held, release = object(), threading.Event(), threading.Event()
        results = {}

        def slow_init_elsewhere():
            with rd._init_lock:
                lock_held.set()
                release.wait(10)

        with patch.dict(rd.PROVIDERS, {"cda": provider}):
            holder = threading.Thread(target=slow_init_elsewhere)
            holder.start()
            lock_held.wait(10)
            user = threading.Thread(target=lambda: results.__setitem__("cda", rd._ensure_provider("cda")))
            user.start()
            user.join(1)
            returned_while_locked = results.get("cda")
            release.set()
            holder.join(10)
            user.join(10)
        self.assertIs(returned_while_locked, provider)


if __name__ == "__main__":
    unittest.main()
