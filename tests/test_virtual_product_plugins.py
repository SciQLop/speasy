import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_PLUGIN_PACKAGE = '''
def register():
    from speasy.virtual_products import register_virtual_product

    @register_virtual_product("virtual/plugin_test/dummy")
    def dummy(start_time, stop_time):
        return None
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


if __name__ == "__main__":
    unittest.main()
