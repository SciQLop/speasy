#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the docs/_generate_cdpp3dview_frames_table.py Sphinx build-time generator,
in particular the fallback path (docs/_cdpp3dview_frames_fallback.json) that's otherwise
never exercised by CI since the live 3DView server is reachable there."""
import json
import os
import sys
import unittest
from unittest import mock

_DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
sys.path.insert(0, _DOCS_DIR)

import _generate_cdpp3dview_frames_table as gen  # noqa: E402


class GenerateFrameTable(unittest.TestCase):
    def setUp(self):
        self._real_output_path = gen.OUTPUT_PATH
        self.addCleanup(setattr, gen, "OUTPUT_PATH", self._real_output_path)

    def _generate_to_temp_file(self, tmp_dir):
        gen.OUTPUT_PATH = os.path.join(tmp_dir, "_generated_frames_table.rst")
        gen.generate()
        with open(gen.OUTPUT_PATH) as f:
            return f.read()

    def test_live_fetch_failure_falls_back_to_snapshot(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch.object(gen, "_fetch_live_frames", side_effect=OSError("network down")):
                content = self._generate_to_temp_file(tmp_dir)
        self.assertIn("cached snapshot", content)

    def test_live_fetch_returning_zero_frames_falls_back_to_snapshot(self):
        """An empty `frames: []` response is a valid-looking but useless table -- it must be
        treated the same as a fetch failure, not rendered as-is."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch.object(gen, "_fetch_live_frames", return_value=[]):
                content = self._generate_to_temp_file(tmp_dir)
        with open(gen.FALLBACK_PATH) as f:
            fallback = json.load(f)
        self.assertTrue(fallback["frames"], "fallback fixture must be non-empty for this test to be meaningful")
        self.assertIn("cached snapshot", content)
        self.assertIn(fallback["frames"][0]["name"], content)


if __name__ == "__main__":
    unittest.main()
