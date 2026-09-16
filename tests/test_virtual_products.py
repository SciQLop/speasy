import unittest
from datetime import datetime, timedelta, timezone

import numpy as np
from ddt import data, ddt

import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex
from speasy.core.time import make_utc_datetime64
from speasy.products.variable import (DataContainer, SpeasyVariable,
                                      VariableTimeAxis)
from speasy.virtual_products import register_virtual_product, registry

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

    def test_register_returns_the_tree_leaf(self):
        node = registry._register("test/dummy", _hourly_ramp)
        self.assertIs(node, spz.inventories.tree.virtual.test.dummy)

    def test_tree_leaf_is_callable(self):
        registry._register("test/dummy", _hourly_ramp)
        var = spz.inventories.tree.virtual.test.dummy(_START, _STOP)
        self.assertIsInstance(var, SpeasyVariable)

    def test_tree_leaf_is_a_virtual_product(self):
        registry._register("test/dummy", _hourly_ramp)
        self.assertIsInstance(spz.inventories.tree.virtual.test.dummy, registry.VirtualProduct)


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


class VirtualProductObject(unittest.TestCase):
    def setUp(self):
        self.product = registry.VirtualProduct(name="dummy", provider="virtual",
                                               uid="test/dummy", callback=_hourly_ramp)

    def test_product_forwards_the_call(self):
        var = self.product(_START, _STOP)
        self.assertIsInstance(var, SpeasyVariable)
        self.assertGreater(len(var), 0)

    def test_product_is_an_inventory_node(self):
        self.assertIsInstance(self.product, ParameterIndex)
        self.assertEqual(self.product.spz_uid(), "test/dummy")
        self.assertEqual(self.product.spz_provider(), "virtual")


class VirtualProductRegistration(unittest.TestCase):
    def setUp(self):
        self.addCleanup(_reset_registry)

    def test_returns_the_tree_leaf(self):
        beta = register_virtual_product("virtual/plasma/beta", _hourly_ramp)
        self.assertIs(beta, spz.inventories.tree.virtual.plasma.beta)

    def test_direct_form_rejects_malformed_path(self):
        with self.assertRaises(ValueError):
            register_virtual_product("plasma/beta", _hourly_ramp)

    def test_decorator_form_rejects_malformed_path(self):
        with self.assertRaises(ValueError):
            register_virtual_product("plasma/beta")

    def test_direct_form_sets_meta_on_the_tree_leaf(self):
        register_virtual_product("virtual/plasma/beta", _hourly_ramp, meta={"units": "nT"})
        self.assertEqual(spz.inventories.tree.virtual.plasma.beta.units, "nT")

    def test_decorator_form_sets_meta_on_the_tree_leaf(self):
        @register_virtual_product("virtual/plasma/beta", meta={"units": "nT"})
        def beta(start_time, stop_time):
            return _hourly_ramp(start_time, stop_time)

        self.assertEqual(beta.units, "nT")


@ddt
class VirtualProductPublicNames(unittest.TestCase):
    @data("register_virtual_product", "UnknownVirtualProduct", "VirtualProductTypeError",
          "VirtualProductCycleError")
    def test_name_is_importable_from_the_package(self, name):
        self.assertIs(getattr(spz.virtual_products, name), getattr(registry, name))


class VirtualProductDecorator(unittest.TestCase):
    def setUp(self):
        self.addCleanup(_reset_registry)

        @register_virtual_product("virtual/plasma/beta")
        def beta(start_time, stop_time):
            return _hourly_ramp(start_time, stop_time)

        self.beta = beta

    def test_decorated_name_is_the_tree_leaf(self):
        self.assertIs(self.beta, spz.inventories.tree.virtual.plasma.beta)

    def test_decorated_name_stays_callable(self):
        self.assertIsInstance(self.beta(_START, _STOP), SpeasyVariable)

    def test_decorated_name_is_accepted_by_get_data(self):
        self.assertIsInstance(spz.get_data(self.beta, _START, _STOP), SpeasyVariable)


class VirtualProductRobustness(unittest.TestCase):
    def setUp(self):
        self.addCleanup(_reset_registry)

    def test_last_registration_wins(self):
        calls = []
        register_virtual_product("virtual/x", lambda s, e: calls.append("first"))
        register_virtual_product("virtual/x", lambda s, e: calls.append("second"))
        spz.get_data("virtual/x", _START, _STOP)
        spz.inventories.tree.virtual.x(_START, _STOP)
        self.assertEqual(calls, ["second", "second"])

    def test_re_registration_warns(self):
        register_virtual_product("virtual/x", _hourly_ramp)
        with self.assertWarnsRegex(UserWarning, "virtual/x"):
            register_virtual_product("virtual/x", _hourly_ramp)

    def test_wrong_return_type_raises(self):
        def returns_array(start_time, stop_time):
            return np.zeros(3)

        register_virtual_product("virtual/bad", returns_array)
        with self.assertRaises(registry.VirtualProductTypeError) as ctx:
            spz.get_data("virtual/bad", _START, _STOP)
        self.assertIn("ndarray", str(ctx.exception))
        self.assertIn("returns_array", str(ctx.exception))

    def test_direct_call_checks_return_type(self):
        def returns_array(start_time, stop_time):
            return np.zeros(3)

        bad = register_virtual_product("virtual/bad", returns_array)
        with self.assertRaises(registry.VirtualProductTypeError) as ctx:
            bad(_START, _STOP)
        self.assertIn("ndarray", str(ctx.exception))
        self.assertIn("returns_array", str(ctx.exception))

    def test_none_return_is_accepted(self):
        register_virtual_product("virtual/empty", lambda s, e: None)
        self.assertIsNone(spz.get_data("virtual/empty", _START, _STOP))

    def test_unknown_path_raises_unknown_virtual_product(self):
        with self.assertRaises(registry.UnknownVirtualProduct):
            spz.get_data("virtual/nope", _START, _STOP)

    def test_unknown_path_suggests_close_paths(self):
        register_virtual_product("virtual/plasma/beta", _hourly_ramp)
        with self.assertRaises(registry.UnknownVirtualProduct) as ctx:
            spz.get_data("virtual/plasma/bet", _START, _STOP)
        self.assertIn("'virtual/plasma/beta'", str(ctx.exception))

    def test_composition_without_cycle_works(self):
        register_virtual_product("virtual/a", _hourly_ramp)
        register_virtual_product("virtual/b", lambda s, e: spz.get_data("virtual/a", s, e))
        self.assertIsInstance(spz.get_data("virtual/b", _START, _STOP), SpeasyVariable)

    def test_cycle_raises_virtual_product_cycle_error(self):
        register_virtual_product("virtual/a", lambda s, e: spz.get_data("virtual/b", s, e))
        register_virtual_product("virtual/b", lambda s, e: spz.get_data("virtual/a", s, e))
        with self.assertRaises(registry.VirtualProductCycleError):
            spz.get_data("virtual/a", _START, _STOP)

    def test_cycle_message_names_the_chain_on_direct_call(self):
        a = register_virtual_product("virtual/a", lambda s, e: spz.get_data("virtual/b", s, e))
        register_virtual_product("virtual/b", lambda s, e: spz.get_data("virtual/a", s, e))
        with self.assertRaises(registry.VirtualProductCycleError) as ctx:
            a(_START, _STOP)
        self.assertIn("virtual/a -> virtual/b -> virtual/a", str(ctx.exception))

    def test_finite_self_composition_works(self):
        one_day = timedelta(days=1)

        def previous_day(start_time, stop_time):
            if start_time <= _START - 3 * one_day:
                return _hourly_ramp(start_time, stop_time)
            return spz.get_data("virtual/c", start_time - one_day, stop_time - one_day)

        register_virtual_product("virtual/c", previous_day)
        self.assertIsInstance(spz.get_data("virtual/c", _START, _STOP), SpeasyVariable)


if __name__ == '__main__':
    unittest.main()
