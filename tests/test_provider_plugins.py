import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import speasy as spz
from speasy.core import dataprovider as dp, plugins
from speasy.core.dataprovider import register_provider
from speasy.core.requests_scheduling import request_dispatch as rd

_PLUGIN_PACKAGE = '''
def register():
    from . import provider


def register_broken():
    from speasy import get_data
'''

_PLUGIN_PROVIDER = '''
from speasy.core.dataprovider import DataProvider, register_provider


@register_provider
class FakeProvider(DataProvider):
    NAME = "fakeprov"
    ALIASES = ("fake",)

    def __init__(self):
        DataProvider.__init__(self, inventory_disable_proxy=True)

    def build_inventory(self, root):
        return root
'''


def _install_fake_plugin(root: Path, entry_points: str):
    """A package plus its .dist-info, enough for importlib.metadata to find its entry points
    once root is on sys.path, without installing anything."""
    package = root / "fakeprov"
    package.mkdir()
    (package / "__init__.py").write_text(_PLUGIN_PACKAGE)
    (package / "provider.py").write_text(_PLUGIN_PROVIDER)
    dist_info = root / "fakeprov-0.1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Metadata-Version: 2.1\nName: fakeprov\nVersion: 0.1\n")
    (dist_info / "entry_points.txt").write_text(f"[speasy.providers]\n{entry_points}\n")


def _run_with_plugin(entry_points, script):
    with tempfile.TemporaryDirectory() as root:
        _install_fake_plugin(Path(root), entry_points)
        python_path = os.pathsep.join(filter(None, [root, os.environ.get("PYTHONPATH")]))
        env = {**os.environ, "SPEASY_SKIP_INIT_PROVIDERS": "1", "PYTHONPATH": python_path}
        return subprocess.run([sys.executable, "-c", textwrap.dedent(script)], env=env,
                              capture_output=True, text=True, timeout=600)


class ProviderEntryPoints(unittest.TestCase):
    def test_plugin_provider_registers_and_starts_on_first_use(self):
        result = _run_with_plugin("fakeprov = fakeprov:register", """
            import speasy as spz
            from speasy.core.requests_scheduling import request_dispatch as rd
            assert "fakeprov" in dir(spz), dir(spz)
            assert "fakeprov" not in rd.PROVIDERS, rd.PROVIDERS
            assert spz.inventories.tree.fakeprov is not None
            assert type(spz.fakeprov).__name__ == "FakeProvider"
            assert spz.fakeprov is rd.PROVIDERS["fake"]
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_broken_plugin_does_not_break_import(self):
        result = _run_with_plugin("fakeprov = fakeprov:register\nbroken = fakeprov:register_broken", """
            import speasy as spz
            assert "fakeprov" in dir(spz), dir(spz)
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Failed to load plugin broken", result.stderr)


class ProviderPluginEdgeCases(unittest.TestCase):
    def setUp(self):
        for namespace in (dp._PROVIDER_CLASSES, rd.__dict__, rd.PROVIDERS):
            patcher = patch.dict(namespace)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_plugin_reusing_a_bundled_name_is_skipped(self):
        def register():
            @register_provider
            class Clash:
                NAME, ALIASES = "cda", ()

        entry_point = MagicMock()
        entry_point.name, entry_point.value = "clash", "clash_pkg:register"
        entry_point.load.return_value = register
        bundled = dp.registered_providers()["cda"]
        with patch.object(plugins, "entry_points", return_value=[entry_point]), \
                self.assertLogs("speasy.core.plugins", "WARNING"):
            plugins.load_plugins("speasy.providers")
        self.assertIs(dp.registered_providers()["cda"], bundled)

    def test_a_provider_registered_after_import_starts_on_first_use(self):
        @register_provider
        class Late:
            NAME, ALIASES = "late", ()

        self.assertIsInstance(spz.late, Late)
        self.assertIs(rd.PROVIDERS["late"], spz.late)


if __name__ == "__main__":
    unittest.main()
