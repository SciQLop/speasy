import os
import subprocess
import sys
import textwrap
import threading
import unittest
from unittest.mock import Mock, patch

import speasy as spz
from speasy.core import dataprovider as dp
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


class _IsolatedProviders(unittest.TestCase):
    # In-process counterpart of the subprocess tests above, provider classes are faked in the registry
    def setUp(self):
        for namespace in (rd.__dict__, rd.PROVIDERS, spz.inventories.tree.__dict__, dp._PROVIDER_CLASSES):
            patcher = patch.dict(namespace)
            patcher.start()
            self.addCleanup(patcher.stop)
        rd.__dict__.pop("cda", None)
        rd.PROVIDERS.clear()
        spz.inventories.tree.__dict__.pop("cda", None)

    @staticmethod
    def _register(cls):
        """Replaces the registered provider of the same main name, aliases included."""
        for name, registered in list(dp._PROVIDER_CLASSES.items()):
            if registered.PROVIDER_NAME == cls.PROVIDER_NAME:
                del dp._PROVIDER_CLASSES[name]
        dp._PROVIDER_CLASSES.update(dict.fromkeys([cls.PROVIDER_NAME, *cls.PROVIDER_ALT_NAMES], cls))
        return cls


class EnsureProvider(_IsolatedProviders):
    def test_alias_initializes_main_provider_once(self):
        built = []

        @self._register
        class Fake:
            PROVIDER_NAME, PROVIDER_ALT_NAMES = "cda", ("cdaweb",)

            def __init__(self):
                built.append(self)

        first = rd._ensure_provider("cdaweb")
        self.assertIs(rd.cda, first)
        self.assertIs(rd._ensure_provider("cda"), first)
        self.assertEqual(len(built), 1)

    def test_inventory_tree_initializes_provider(self):
        inventory, built = object(), []

        @self._register
        class Fake:
            PROVIDER_NAME, PROVIDER_ALT_NAMES = "cda", ()

            def __init__(self):
                built.append(self)
                spz.inventories.tree.__dict__["cda"] = inventory

        self.assertIs(spz.inventories.tree.cda, inventory)
        with self.assertRaises(AttributeError):
            spz.inventories.tree._private
        self.assertEqual(len(built), 1)

    def test_concurrent_first_use_waits_for_init(self):
        started, release = threading.Event(), threading.Event()

        @self._register
        class SlowProvider:
            PROVIDER_NAME, PROVIDER_ALT_NAMES = "cda", ()

            def __init__(self):
                started.set()
                release.wait(10)

        results = {}

        def first_use(key):
            results[key] = rd._ensure_provider("cda")

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

        rd.PROVIDERS["cda"] = provider
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


class ProviderAccessors(_IsolatedProviders):
    def test_init_accessor_resolves_aliases(self):
        @self._register
        class Fake:
            PROVIDER_NAME, PROVIDER_ALT_NAMES = "cda", ("cdaweb",)

        rd.init_cdaweb()
        self.assertIsInstance(rd.cda, Fake)

    def test_unknown_init_accessor_raises(self):
        with self.assertRaises(AttributeError):
            rd.init_nope

    def test_dir_lists_registered_providers_and_their_init_accessors(self):
        @self._register
        class Fake:
            PROVIDER_NAME, PROVIDER_ALT_NAMES = "fakeprov", ()

        self.assertTrue({"fakeprov", "init_fakeprov", "init_amda"} <= set(dir(rd)))
        self.assertIn("fakeprov", dir(spz))

    def test_speasy_attribute_follows_a_retry(self):
        rd.__dict__["amda"] = None

        @self._register
        class FakeAmda:
            PROVIDER_NAME, PROVIDER_ALT_NAMES = "amda", ()

        rd.init_amda()
        self.assertIsInstance(spz.amda, FakeAmda)


if __name__ == "__main__":
    unittest.main()
