import unittest
from datetime import datetime, timezone

import numpy as np
from ddt import data, ddt

import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex
from speasy.core.time import make_utc_datetime64
from speasy.products.variable import (DataContainer, SpeasyVariable,
                                      VariableTimeAxis)
from speasy.virtual_products import registry

_START = datetime(2016, 10, 10, tzinfo=timezone.utc)
_STOP = datetime(2016, 10, 11, tzinfo=timezone.utc)


def _hourly_ramp(start_time, stop_time):
    """Stands in for a user callback: one point per hour over the requested window."""
    time = np.arange(make_utc_datetime64(start_time), make_utc_datetime64(stop_time),
                     np.timedelta64(1, 'h'))
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                          values=DataContainer(values=np.arange(len(time), dtype=float), meta=None),
                          columns=["Values"])


def _reset_registry():
    """Leave no registered product behind: tests share the module level registry."""
    registry._callbacks.clear()
    registry._root.clear()
    registry._flat_inventory.clear()


class VirtualProviderRegistration(unittest.TestCase):
    def test_virtual_provider_is_registered(self):
        self.assertIn("virtual", spz.list_providers())


class VirtualProductGetData(unittest.TestCase):
    def setUp(self):
        self.addCleanup(_reset_registry)
        registry._register("test/dummy", _hourly_ramp)

    def test_get_data_returns_product(self):
        var = spz.get_data("virtual/test/dummy", _START, _STOP)
        self.assertIsInstance(var, SpeasyVariable)
        self.assertGreater(len(var), 0)

    def test_values_inside_time_window(self):
        var = spz.get_data("virtual/test/dummy", _START, _STOP)
        self.assertGreaterEqual(var.time[0], make_utc_datetime64(_START))
        self.assertLessEqual(var.time[-1], make_utc_datetime64(_STOP))

    def test_tree_node_or_path_are_equivalent(self):
        by_path = spz.get_data("virtual/test/dummy", _START, _STOP)
        by_node = spz.get_data(spz.inventories.tree.virtual.test.dummy, _START, _STOP)
        self.assertEqual(len(by_path), len(by_node))


class VirtualProductInventory(unittest.TestCase):
    def setUp(self):
        self.addCleanup(_reset_registry)

    def test_virtual_branch_exists(self):
        self.assertIsInstance(spz.inventories.tree.virtual, SpeasyIndex)

    def test_product_appears_in_tree(self):
        registry._register("test/dummy", _hourly_ramp)
        self.assertIsInstance(spz.inventories.tree.virtual.test.dummy, ParameterIndex)

    def test_leaf_carries_the_full_uid(self):
        registry._register("test/dummy", _hourly_ramp)
        self.assertEqual(spz.inventories.tree.virtual.test.dummy.spz_uid(), "test/dummy")

    def test_deep_path_digs_every_folder(self):
        registry._register("test/deep/dummy", _hourly_ramp)
        self.assertIsInstance(spz.inventories.tree.virtual.test.deep.dummy, ParameterIndex)

    def test_product_appears_in_flat_inventory(self):
        registry._register("test/dummy", _hourly_ramp)
        node = spz.inventories.flat_inventories.virtual.parameters["test/dummy"]
        self.assertIs(node, spz.inventories.tree.virtual.test.dummy)


@ddt
class VirtualProductPath(unittest.TestCase):
    def test_strips_the_provider_prefix(self):
        self.assertEqual(registry._path_to_uid("virtual/plasma/beta"), "plasma/beta")

    def test_keeps_a_single_segment_uid(self):
        self.assertEqual(registry._path_to_uid("virtual/beta"), "beta")

    @data("plasma/beta",           # missing 'virtual/' prefix
          "amda/imf_gsm",          # bad provider name
          "virtual",               # no uid at all
          "virtual/",              # empty uid
          "virtual/plasma//beta",  # empty segment
          "virtual/plasma/beta/",  # trailing slash
          "",
          "   ")
    def test_rejects_malformed_path(self, path):
        with self.assertRaises(ValueError):
            registry._path_to_uid(path)

    @data(None, 42, ["virtual", "beta"])
    def test_rejects_non_string_path(self, path):
        with self.assertRaises(TypeError):
            registry._path_to_uid(path)


if __name__ == '__main__':
    unittest.main()
