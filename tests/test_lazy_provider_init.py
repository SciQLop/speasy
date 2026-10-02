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
    env = {**os.environ, "SPEASY_CORE_DISABLED_PROVIDERS": disabled}
    env.pop("SPEASY_SKIP_INIT_PROVIDERS", None)
    return subprocess.run([sys.executable, "-c", textwrap.dedent(script)], env=env,
                          capture_output=True, text=True, timeout=600)


class LazyProviderInit(unittest.TestCase):
    def test_import_starts_no_provider(self):
        result = _run("""
            import speasy as spz
            from speasy.core.requests_scheduling.request_dispatch import PROVIDERS
            assert PROVIDERS == {}, PROVIDERS
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_list_providers_names_enabled_providers_without_starting_them(self):
        result = _run("""
            import speasy as spz
            from speasy.core.requests_scheduling.request_dispatch import PROVIDERS
            expected = {"csa", "cda", "cdaweb", "ssc", "sscweb", "archive", "generic_archive", "file",
                        "uiowaephtool", "UiowaEphTool", "cdpp3dview", "3DView"}
            assert set(spz.list_providers()) == expected, spz.list_providers()
            assert PROVIDERS == {}, PROVIDERS
        """, disabled="amda")
        self.assertEqual(result.returncode, 0, result.stderr)

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
            assert set(PROVIDERS) == {"archive", "generic_archive", "file"}, PROVIDERS
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_disabling_a_provider_by_alias(self):
        for alias, main_name in (("cdaweb", "cda"), ("file", "archive")):
            with self.subTest(alias):
                result = _run(f"""
                    import speasy as spz
                    assert spz.{main_name} is None
                    assert not hasattr(spz.inventories.tree, "{main_name}")
                """, disabled=alias)
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
            if registered.NAME == cls.NAME:
                del dp._PROVIDER_CLASSES[name]
        dp._PROVIDER_CLASSES.update(dict.fromkeys([cls.NAME, *cls.ALIASES], cls))
        return cls


class EnsureProvider(_IsolatedProviders):
    def test_alias_initializes_main_provider_once(self):
        built = []

        @self._register
        class Fake:
            NAME, ALIASES = "cda", ("cdaweb",)

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
            NAME, ALIASES = "cda", ()

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
            NAME, ALIASES = "cda", ()

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


class UnavailableProviderErrors(_IsolatedProviders):
    def test_disabled_provider_error_says_how_to_enable_it(self):
        @self._register
        class Fake:
            NAME, ALIASES = "cda", ("cdaweb",)

        with patch.object(rd.core_cfg, "disabled_providers", return_value={"cdaweb"}), \
                self.assertRaisesRegex(ValueError, r"'cda' is disabled.*disabled_providers"):
            rd.get_data("cda/some_product", "2020-01-01", "2020-01-02")

    def test_failed_provider_error_says_how_to_retry(self):
        @self._register
        class Broken:
            NAME, ALIASES = "cda", ()

            def __init__(self):
                raise ConnectionError("server unreachable")

        with self.assertLogs(rd.log, "WARNING"), \
                self.assertRaisesRegex(ValueError, r"'cda' failed to start.*update_inventories\(\)"):
            rd.get_data("cda/some_product", "2020-01-01", "2020-01-02")


class ProviderAccessors(_IsolatedProviders):
    def test_init_accessor_resolves_aliases(self):
        @self._register
        class Fake:
            NAME, ALIASES = "cda", ("cdaweb",)

        rd.init_cdaweb()
        self.assertIsInstance(rd.cda, Fake)

    def test_unknown_init_accessor_raises(self):
        with self.assertRaises(AttributeError):
            rd.init_nope

    def test_dir_lists_registered_providers_and_their_init_accessors(self):
        @self._register
        class Fake:
            NAME, ALIASES = "fakeprov", ()

        self.assertLessEqual({"fakeprov", "init_fakeprov", "init_amda"}, set(dir(rd)))
        self.assertIn("fakeprov", dir(spz))

    def test_speasy_attribute_follows_a_retry(self):
        rd.__dict__["amda"] = None

        @self._register
        class FakeAmda:
            NAME, ALIASES = "amda", ()

        rd.init_amda()
        self.assertIsInstance(spz.amda, FakeAmda)


if __name__ == "__main__":
    unittest.main()
