import os
import subprocess
import sys
import tempfile
import textwrap
import traceback
import unittest
from pathlib import Path
from unittest import mock

from speasy.virtual_products import registry
from tests.test_virtual_products import _reset_registry

_PLUGIN_PACKAGE = '''
def register():
    from speasy.virtual_products import register_virtual_product

    @register_virtual_product("virtual/plugin_test/dummy")
    def dummy(start_time, stop_time):
        return None


def register_broken():
    raise RuntimeError("broken on purpose")
'''


def _install_fake_plugin(root: Path, entry_points: str):
    """A package plus its .dist-info, enough for importlib.metadata to find its entry points
    once root is on sys.path, without installing anything."""
    package = root / "fakevp"
    package.mkdir()
    (package / "__init__.py").write_text(_PLUGIN_PACKAGE)
    dist_info = root / "fakevp-0.1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Metadata-Version: 2.1\nName: fakevp\nVersion: 0.1\n")
    (dist_info / "entry_points.txt").write_text(f"[speasy.virtual_products]\n{entry_points}\n")


def _run_with_plugin(entry_points, script):
    with tempfile.TemporaryDirectory() as root:
        _install_fake_plugin(Path(root), entry_points)
        python_path = os.pathsep.join(filter(None, [root, os.environ.get("PYTHONPATH")]))
        env = {**os.environ, "SPEASY_SKIP_INIT_PROVIDERS": "1", "PYTHONPATH": python_path}
        return subprocess.run([sys.executable, "-c", textwrap.dedent(script)], env=env,
                              capture_output=True, text=True, timeout=600)


class VirtualProductEntryPoints(unittest.TestCase):
    def test_plugin_virtual_product_is_in_the_tree(self):
        result = _run_with_plugin("fakevp = fakevp:register", """
            import speasy as spz
            node = spz.inventories.tree.virtual.plugin_test.dummy
            assert node.spz_uid() == "plugin_test/dummy", node.spz_uid()
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_broken_plugin_does_not_break_import(self):
        result = _run_with_plugin("fakevp = fakevp:register\nbroken = fakevp:register_broken", """
            import speasy as spz
            spz.inventories.tree.virtual.plugin_test.dummy
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Failed to load speasy.virtual_products plugin broken", result.stderr)


_USER_VP_UID = "user_dir_test/beta"

_USER_VP_FILE = f'''
from speasy.virtual_products import register_virtual_product


@register_virtual_product("virtual/{_USER_VP_UID}")
def beta(start_time, stop_time):
    return None
'''


def _run_with_user_dir(vp_source, script):
    with tempfile.TemporaryDirectory() as vp_dir:
        Path(vp_dir, "user_vp.py").write_text(vp_source)
        env = {**os.environ, "SPEASY_SKIP_INIT_PROVIDERS": "1", "SPEASY_CORE_USER_VP_EXTRA_DIRS": vp_dir}
        return subprocess.run([sys.executable, "-c", textwrap.dedent(script)], env=env,
                              capture_output=True, text=True, timeout=600)


class VirtualProductUserDirs(unittest.TestCase):
    def setUp(self):
        self.addCleanup(_reset_registry)

    def test_a_vp_file_in_an_extra_dir_is_registered(self):
        with tempfile.TemporaryDirectory() as vp_dir:
            Path(vp_dir, "beta.py").write_text(_USER_VP_FILE)
            with mock.patch.object(registry, "user_vp_dir", return_value="/nonexistent"):
                with mock.patch.object(registry.cfg.user_vp_extra_dirs, "get", return_value={vp_dir}):
                    registry.load_extra_vp()
        self.assertIn(_USER_VP_UID, registry._flat_inventory.parameters)

    def test_a_broken_vp_file_is_skipped_and_the_valid_one_still_loads(self):
        with tempfile.TemporaryDirectory() as vp_dir:
            Path(vp_dir, "a_broken.py").write_text("raise RuntimeError('this vp file is broken')\n")
            Path(vp_dir, "beta.py").write_text(_USER_VP_FILE)
            with mock.patch.object(registry, "user_vp_dir", return_value="/nonexistent"):
                with mock.patch.object(registry.cfg.user_vp_extra_dirs, "get", return_value={vp_dir}):
                    with self.assertLogs("speasy.virtual_products.registry", level="WARNING") as captured:
                        registry.load_extra_vp()
        self.assertTrue(any("a_broken.py" in line for line in captured.output))
        self.assertIn(_USER_VP_UID, registry._flat_inventory.parameters)

    def test_the_traceback_points_to_the_broken_vp_file(self):
        with tempfile.TemporaryDirectory() as vp_dir:
            broken = Path(vp_dir, "a_broken.py")
            broken.write_text("raise RuntimeError('this vp file is broken')\n")
            with mock.patch.object(registry, "user_vp_dir", return_value="/nonexistent"):
                with mock.patch.object(registry.cfg.user_vp_extra_dirs, "get", return_value={vp_dir}):
                    with self.assertLogs("speasy.virtual_products.registry", level="WARNING") as captured:
                        registry.load_extra_vp()
        _, _, tb = captured.records[0].exc_info
        self.assertEqual(traceback.extract_tb(tb)[-1].filename, str(broken))

    def test_import_speasy_loads_the_user_vp_files(self):
        result = _run_with_user_dir(_USER_VP_FILE, f"""
            import speasy as spz
            node = spz.inventories.tree.virtual.user_dir_test.beta
            assert node.spz_uid() == "{_USER_VP_UID}", node.spz_uid()
        """)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
