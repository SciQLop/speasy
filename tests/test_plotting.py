#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the matplotlib plotting backend."""
import unittest

import matplotlib.pyplot as plt
import numpy as np

from speasy.plotting.mpl_backend import Plot


class MplBackendLine(unittest.TestCase):
    def setUp(self):
        self.addCleanup(plt.close, "all")

    def test_forwards_extra_kwargs_to_matplotlib(self):
        """line() declares *args/**kwargs but used to never pass them to
        ax.plot(), so e.g. b.plot(linestyle="--") was silently a no-op.
        """
        x = np.arange(10)
        y = np.stack([np.arange(10), np.arange(10) + 1], axis=1)

        ax = Plot().line(x, y, labels=["a", "b"], linestyle="--", linewidth=3)

        lines = ax.get_lines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertEqual(line.get_linestyle(), "--")
            self.assertEqual(line.get_linewidth(), 3)


class MplBackendColormap(unittest.TestCase):
    def setUp(self):
        self.addCleanup(plt.close, "all")

    def _xyz(self):
        x = np.arange(5)
        y = np.arange(4)
        z = np.array([[1., 2., 3., 4., 5.],
                     [2., 3., 4., 5., 6.],
                     [3., 4., 5., 6., 7.],
                     [4., 5., 6., 7., 8.]])
        return x, y, z

    def test_respects_explicit_vmin_zero(self):
        """vmin = vmin or np.nanmin(...) treats an explicit vmin=0 as falsy
        and silently replaces it with the computed nanmin.
        """
        x, y, z = self._xyz()
        ax = Plot().colormap(x, y, z, vmin=0, logz=False)
        mesh = ax.collections[0]
        self.assertEqual(mesh.norm.vmin, 0)

    def test_respects_explicit_vmax_zero(self):
        x, y, z = self._xyz()
        ax = Plot().colormap(x, y, -z, vmax=0, logz=False)
        mesh = ax.collections[0]
        self.assertEqual(mesh.norm.vmax, 0)


if __name__ == "__main__":
    unittest.main()
