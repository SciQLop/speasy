import copy
import dataclasses
import operator
import unittest
from unittest import mock

import numpy as np
from ddt import data, ddt, unpack

import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex
from speasy.virtual_products import interpolate, register_virtual_product, resample
from speasy.virtual_products.expression import (Const, Interpolate, Leaf, Op, Resample, TimeAxisMismatch, bind,
                                                 collect, evaluate, fetch, parse_dt, walk)
from speasy.products.variable import DataContainer, SpeasyVariable, VariableAxis, VariableTimeAxis
from tests.test_virtual_products import _reset_registry

_T0 = np.datetime64("2016-10-10T00:00", "ns")


def _make_variable(values, start=_T0, step=np.timedelta64(1, "h"), meta=None):
    """Synthetic SpeasyVariable: the given values, one point per step from start."""
    values = np.asarray(values, dtype=float)
    time = start + np.arange(len(values)) * step
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                          values=DataContainer(values=values, meta=meta),
                          columns=["Values"])


def _make_3d_variable():
    """Synthetic 3-D SpeasyVariable: time x energy x angle."""
    time = _T0 + np.arange(3) * np.timedelta64(1, "h")
    return SpeasyVariable(axes=[VariableTimeAxis(values=time),
                                VariableAxis(values=np.arange(4.), name="energy"),
                                VariableAxis(values=np.arange(2.), name="angle")],
                          values=DataContainer(values=np.ones((3, 4, 2)), meta=None))


class TestNodes(unittest.TestCase):
    def setUp(self):
        self.index = ParameterIndex(name="mms1_fgm_b_gse_srvy_l2", provider="cda",
                                    uid="mms1_fgm_b_gse_srvy_l2")
        self.leaf = Leaf(self.index)
        self.const = Const(10)

    def test_leaf_keeps_its_index(self):
        self.assertIs(self.leaf.index, self.index)

    def test_leaf_is_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.leaf.index = None

    def test_const_keeps_its_value(self):
        self.assertEqual(self.const.value, 10)

    def test_const_is_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.const.value = 3

    def test_op_keeps_its_ufunc_and_operands(self):
        op = Op(np.multiply, (self.const, self.leaf))
        self.assertIs(op.ufunc, np.multiply)
        self.assertEqual(op.operands, (self.const, self.leaf))

    def test_op_is_frozen(self):
        op = Op(np.multiply, (self.const, self.leaf))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            op.ufunc = np.add


@ddt
class TestRepr(unittest.TestCase):
    def setUp(self):
        self.leaf = Leaf(ParameterIndex(name="mms1_fgm_b_gse_srvy_l2", provider="cda",
                                        uid="mms1_fgm_b_gse_srvy_l2"))
        self.const = Const(10)

    def test_leaf_is_provider_slash_uid(self):
        self.assertEqual(repr(self.leaf), "cda/mms1_fgm_b_gse_srvy_l2")

    def test_leaf_of_a_path_string_is_the_string(self):
        self.assertEqual(repr(Leaf("amda/mms1_dis_ni")), "amda/mms1_dis_ni")

    def test_const_is_the_value(self):
        self.assertEqual(repr(self.const), "10")

    @data((np.add, "+"), (np.subtract, "-"), (np.multiply, "*"),
          (np.divide, "/"), (np.power, "**"))
    @unpack
    def test_binary_op_is_infix(self, ufunc, symbol):
        op = Op(ufunc, (self.const, self.leaf))
        self.assertEqual(repr(op), f"10 {symbol} cda/mms1_fgm_b_gse_srvy_l2")

    def test_lower_precedence_operand_is_parenthesized(self):
        n = Leaf("amda/mms1_dis_ni")
        op = Op(np.multiply, (self.const, Op(np.add, (self.leaf, n))))
        self.assertEqual(repr(op), "10 * (cda/mms1_fgm_b_gse_srvy_l2 + amda/mms1_dis_ni)")

    def test_same_precedence_right_operand_is_parenthesized(self):
        n = Leaf("amda/mms1_dis_ni")
        op = Op(np.subtract, (self.leaf, Op(np.subtract, (n, self.leaf))))
        self.assertEqual(repr(op), "cda/mms1_fgm_b_gse_srvy_l2 - (amda/mms1_dis_ni - cda/mms1_fgm_b_gse_srvy_l2)")

    def test_power_left_operand_is_parenthesized(self):
        op = Op(np.power, (Op(np.power, (self.leaf, Const(2))), Const(3)))
        self.assertEqual(repr(op), "(cda/mms1_fgm_b_gse_srvy_l2 ** 2) ** 3")

    def test_power_right_operand_is_not_parenthesized(self):
        op = Op(np.power, (self.leaf, Op(np.power, (Const(2), Const(3)))))
        self.assertEqual(repr(op), "cda/mms1_fgm_b_gse_srvy_l2 ** 2 ** 3")

    def test_negative_is_prefix(self):
        op = Op(np.negative, (self.leaf,))
        self.assertEqual(repr(op), "-cda/mms1_fgm_b_gse_srvy_l2")

    def test_absolute_is_a_call(self):
        op = Op(np.absolute, (self.leaf,))
        self.assertEqual(repr(op), "abs(cda/mms1_fgm_b_gse_srvy_l2)")

    def test_unary_parentheses_follow_python(self):
        b, n = Leaf("cda/b"), Leaf("amda/n")
        neg_b = Op(np.negative, (b,))
        cases = [
            (Op(np.negative, (Op(np.add, (b, n)),)), "-(cda/b + amda/n)"),
            (Op(np.multiply, (self.const, neg_b)), "10 * -cda/b"),
            (Op(np.power, (neg_b, Const(2))), "(-cda/b) ** 2"),
            (Op(np.negative, (Op(np.power, (b, Const(2))),)), "-cda/b ** 2"),
            (Op(np.negative, (neg_b,)), "--cda/b"),
            (Op(np.power, (b, neg_b)), "cda/b ** (-cda/b)"),
            (Op(np.absolute, (Op(np.add, (b, n)),)), "abs(cda/b + amda/n)"),
            (Op(np.power, (Op(np.absolute, (b,)), Const(2))), "abs(cda/b) ** 2"),
        ]
        for op, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(repr(op), expected)


_OPERATORS = ((operator.add, np.add), (operator.sub, np.subtract),
              (operator.mul, np.multiply), (operator.truediv, np.divide))


@ddt
class TestOperators(unittest.TestCase):
    """Nodes (Leaf, Const, Op) are dataclasses with eq=False: == compares identity,
    so two Op built separately are never equal. Tests compare fields instead."""

    def setUp(self):
        self.index = ParameterIndex(name="mms1_fgm_b_gse_srvy_l2", provider="cda",
                                    uid="mms1_fgm_b_gse_srvy_l2")

    @data(*_OPERATORS)
    @unpack
    def test_index_on_the_left_builds_an_op(self, python_op, ufunc):
        op = python_op(self.index, 10)
        self.assertIs(op.ufunc, ufunc)
        leaf, const = op.operands
        self.assertIs(leaf.index, self.index)
        self.assertEqual(const.value, 10)

    @data(*_OPERATORS)
    @unpack
    def test_index_on_the_right_builds_an_op(self, python_op, ufunc):
        op = python_op(10, self.index)
        self.assertIs(op.ufunc, ufunc)
        const, leaf = op.operands
        self.assertEqual(const.value, 10)
        self.assertIs(leaf.index, self.index)

    @data(*_OPERATORS)
    @unpack
    def test_node_on_the_left_builds_an_op(self, python_op, ufunc):
        op_node = 10 * self.index  # Op(np.multiply, (Const(10), Leaf(B)))
        op = python_op(op_node, self.index)  # e.g. 10 * B + B
        self.assertIs(op.ufunc, ufunc)
        left, right = op.operands
        self.assertIs(left, op_node)  # the existing node is kept as is
        self.assertIs(right.index, self.index)

    @data(*_OPERATORS)
    @unpack
    def test_node_on_the_right_builds_an_op(self, python_op, ufunc):
        op_node = 10 * self.index  # Op(np.multiply, (Const(10), Leaf(B)))
        op = python_op(2, op_node)  # e.g. 2 + 10 * B
        self.assertIs(op.ufunc, ufunc)
        const, right = op.operands
        self.assertEqual(const.value, 2)
        self.assertIs(right, op_node)  # the existing node is kept as is

    def test_index_equality_is_unchanged(self):
        same = ParameterIndex(name="mms1_fgm_b_gse_srvy_l2", provider="cda",
                              uid="mms1_fgm_b_gse_srvy_l2")
        self.assertIs(self.index == same, True)

    def test_index_is_still_unhashable(self):
        with self.assertRaises(TypeError):
            hash(self.index)


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.index = ParameterIndex(name="mms1_fgm_b_gse_srvy_l2", provider="cda",
                                    uid="mms1_fgm_b_gse_srvy_l2")

    def test_ten_times_a_product_gives_that_product(self):
        self.assertEqual(collect(10 * self.index), [self.index])

    def test_same_product_twice_gives_one_leaf(self):
        self.assertEqual(collect(self.index + self.index), [self.index])

    def test_nested_expression_gives_one_leaf(self):
        leaf = Leaf(self.index)
        ten_times = Op(np.multiply, (Const(10), leaf))
        expression = Op(np.add, (ten_times, leaf))
        self.assertEqual(collect(expression), [self.index])

    def test_same_provider_and_uid_is_the_same_product(self):
        renamed = copy.copy(self.index)
        renamed.__spz_name__ = "another_name"
        self.assertEqual(collect(self.index + renamed), [self.index])

    def test_goes_through_a_resample_directive(self):
        [b1s] = resample([self.index], "1s")
        self.assertEqual(collect(b1s), [self.index])

    def test_interpolate_gives_the_reference_and_the_product(self):
        n = ParameterIndex(name="n", provider="amda", uid="n")
        [n_on_b] = interpolate(self.index, [n])
        self.assertEqual(collect(n_on_b), [self.index, n])

    def test_interpolate_on_itself_gives_one_leaf(self):
        [b_on_b] = interpolate(self.index, [self.index])
        self.assertEqual(collect(b_on_b), [self.index])


class TestFetch(unittest.TestCase):
    def test_asks_for_all_products_in_one_call(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b, n = _make_variable([1, 2, 3]), _make_variable([4, 5, 6])
        with mock.patch("speasy.get_data", return_value=[b, n]) as get_data:
            result = fetch([b_index, n_index], "2016-10-10", "2016-10-11")
        get_data.assert_called_once_with([b_index, n_index], "2016-10-10", "2016-10-11")
        self.assertEqual(result, [b, n])


class TestBind(unittest.TestCase):
    def test_maps_each_product_key_to_its_data(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b, n = _make_variable([1, 2, 3]), _make_variable([4, 5, 6])
        self.assertEqual(bind([b_index, n_index], [b, n]),
                         {("cda", "b"): b, ("amda", "n"): n})

    def test_a_product_without_data_gives_none(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b = _make_variable([1, 2, 3])
        self.assertIsNone(bind([b_index, n_index], [b, None]))


class TestWalk(unittest.TestCase):
    def test_ten_times_a_product(self):
        index = ParameterIndex(name="b", provider="cda", uid="b")
        b = _make_variable([1, 2, 3])
        result = walk(10 * index, {("cda", "b"): b}, _T0, _T0 + np.timedelta64(3, "h"))
        np.testing.assert_array_equal(result.values, [[10.], [20.], [30.]])
        np.testing.assert_array_equal(result.time, b.time)

    def test_different_time_axes_raise(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        data = {("cda", "b"): _make_variable([1, 2, 3]), ("amda", "n"): _make_variable([4, 5])}
        with self.assertRaises(TimeAxisMismatch):
            walk(b_index + n_index, data, _T0, _T0 + np.timedelta64(3, "h"))

    def test_time_axis_mismatch_message(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        data = {("cda", "b"): _make_variable([1, 2, 3]), ("amda", "n"): _make_variable([4, 5])}
        with self.assertRaises(TimeAxisMismatch) as caught:
            walk(b_index + n_index, data, _T0, _T0 + np.timedelta64(3, "h"))
        self.assertEqual(str(caught.exception),
                         "cannot combine\n"
                         "  'cda/b'   (3600 s, 3 points)\n"
                         "  'amda/n'  (3600 s, 2 points)\n"
                         "in expression 'cda/b + amda/n'.\n"
                         "Add an explicit directive, e.g.:\n"
                         '  b, n = speasy.virtual_products.resample([B, N], "1s")')

    def test_variables_with_different_starts_share_one_grid(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        late_start = _T0 + np.timedelta64(30, "m")
        data = {("cda", "b"): _make_variable([1, 2, 3, 4]),
                ("amda", "n"): _make_variable([1, 2, 3, 4], start=late_start)}
        b1h, n1h = resample([b_index, n_index], "1h")
        start, stop = _T0, _T0 + np.timedelta64(3, "h")
        grid = _T0 + np.arange(3) * np.timedelta64(1, "h")
        np.testing.assert_array_equal(walk(b1h, data, start, stop).time, grid)
        np.testing.assert_array_equal(walk(n1h, data, start, stop).time, grid)
        np.testing.assert_allclose(walk(b1h, data, start, stop).values, [[1.], [2.], [3.]])
        np.testing.assert_allclose(walk(n1h, data, start, stop).values, [[1.], [1.5], [2.5]])

    def test_interpolate_puts_the_product_on_the_time_axis_of_the_reference(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b = _make_variable([10, 20, 30], start=_T0 + np.timedelta64(30, "m"))
        data = {("cda", "b"): b, ("amda", "n"): _make_variable([1, 2, 3, 4])}
        [n_on_b] = interpolate(b_index, [n_index])
        result = walk(n_on_b, data, _T0, _T0 + np.timedelta64(4, "h"))
        np.testing.assert_array_equal(result.time, b.time)
        np.testing.assert_allclose(result.values, [[1.5], [2.5], [3.5]])

    def test_interpolated_product_combines_with_its_reference(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b = _make_variable([10, 20, 30], start=_T0 + np.timedelta64(30, "m"))
        data = {("cda", "b"): b, ("amda", "n"): _make_variable([1, 2, 3, 4])}
        [n_on_b] = interpolate(b_index, [n_index])
        result = walk(b_index + n_on_b, data, _T0, _T0 + np.timedelta64(4, "h"))
        np.testing.assert_allclose(result.values, [[11.5], [22.5], [33.5]])

    def test_resampling_a_3d_variable_is_not_supported(self):
        s_index = ParameterIndex(name="s", provider="cda", uid="s")
        data = {("cda", "s"): _make_3d_variable()}
        [s1h] = resample([s_index], "1h")
        with self.assertRaisesRegex(ValueError, "not supported"):
            walk(s1h, data, _T0, _T0 + np.timedelta64(3, "h"))

    def test_interpolating_a_3d_variable_is_not_supported(self):
        b_index = ParameterIndex(name="b", provider="cda", uid="b")
        s_index = ParameterIndex(name="s", provider="amda", uid="s")
        data = {("cda", "b"): _make_variable([1, 2, 3]), ("amda", "s"): _make_3d_variable()}
        [s_on_b] = interpolate(b_index, [s_index])
        with self.assertRaisesRegex(ValueError, "not supported"):
            walk(s_on_b, data, _T0, _T0 + np.timedelta64(3, "h"))


class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.index = ParameterIndex(name="mms1_fgm_b_gse_srvy_l2", provider="cda",
                                    uid="mms1_fgm_b_gse_srvy_l2")

    def test_ten_times_a_product(self):
        b = _make_variable([1, 2, 3])
        with mock.patch("speasy.get_data", return_value=[b]) as get_data:
            result = evaluate(10 * self.index, "2016-10-10", "2016-10-11")
        get_data.assert_called_once_with([self.index], "2016-10-10", "2016-10-11")
        np.testing.assert_array_equal(result.values, [[10.], [20.], [30.]])
        np.testing.assert_array_equal(result.time, b.time)

    def test_result_is_named_after_the_expression(self):
        b = _make_variable([1, 2, 3])
        with mock.patch("speasy.get_data", return_value=[b]):
            result = evaluate(10 * self.index, "2016-10-10", "2016-10-11")
        self.assertEqual(result.name, "10 * cda/mms1_fgm_b_gse_srvy_l2")

    def test_a_product_without_data_gives_none(self):
        with mock.patch("speasy.get_data", return_value=[None]):
            result = evaluate(10 * self.index, "2016-10-10", "2016-10-11")
        self.assertIsNone(result)

    def test_two_cadences_with_resample(self):
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b = _make_variable([1, 3, 6, 9], step=np.timedelta64(30, "m"))
        n = _make_variable([2, 4, 8])
        b_30m, n_30m = resample([self.index, n_index], "30min")
        with mock.patch("speasy.get_data", return_value=[b, n]) as get_data:
            result = evaluate(10 * b_30m / n_30m, "2016-10-10", "2016-10-10T02:00")
        get_data.assert_called_once_with([self.index, n_index], "2016-10-10", "2016-10-10T02:00")
        np.testing.assert_array_equal(result.time, b.time)
        np.testing.assert_allclose(result.values, [[5.], [10.], [15.], [15.]])

    def test_two_cadences_with_interpolate(self):
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b = _make_variable([1, 3, 6, 9], step=np.timedelta64(30, "m"))
        n = _make_variable([2, 4, 8])
        [n_on_b] = interpolate(self.index, [n_index])
        with mock.patch("speasy.get_data", return_value=[b, n]) as get_data:
            result = evaluate(10 * self.index / n_on_b, "2016-10-10", "2016-10-10T02:00")
        get_data.assert_called_once_with([self.index, n_index], "2016-10-10", "2016-10-10T02:00")
        np.testing.assert_array_equal(result.time, b.time)
        np.testing.assert_allclose(result.values, [[5.], [10.], [15.], [15.]])

    def test_result_drops_fill_and_valid_range_metadata(self):
        b = _make_variable([1, 2, 3], meta={"CATDESC": "B field", "FILLVAL": -1e31,
                                            "VALIDMIN": 0, "VALIDMAX": 100})
        with mock.patch("speasy.get_data", return_value=[b]):
            result = evaluate(10 * self.index, "2016-10-10", "2016-10-11")
        self.assertEqual(result.meta, {"CATDESC": "B field"})


class TestRegisteredExpression(unittest.TestCase):
    def setUp(self):
        self.addCleanup(_reset_registry)
        self.index = ParameterIndex(name="mms1_fgm_b_gse_srvy_l2", provider="cda",
                                    uid="mms1_fgm_b_gse_srvy_l2")

    def test_get_data_serves_a_registered_expression(self):
        b = _make_variable([1, 2, 3])
        register_virtual_product("virtual/test/mag_10", 10 * self.index)
        # Patch only the 'spz' imported by expression.py and not speasy.get_data itself:
        # the outer get_data below stays real so it routes to the virtual
        # provider and into evaluate_expression; only the inner fetch of B is
        # faked so it doesnt try a network  access.
        with mock.patch("speasy.virtual_products.expression.spz") as fake_spz:
            fake_spz.get_data.return_value = [b]
            result = spz.get_data("virtual/test/mag_10", "2016-10-10", "2016-10-11")
        np.testing.assert_array_equal(result.values, [[10.], [20.], [30.]])
        np.testing.assert_array_equal(result.time, b.time)

    def test_two_cadences_expression_is_served_under_its_name(self):
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b = _make_variable([1, 3, 6, 9], step=np.timedelta64(30, "m"))
        n = _make_variable([2, 4, 8])
        b_30m, n_30m = resample([self.index, n_index], "30min")
        product = register_virtual_product("virtual/test/ratio", 10 * b_30m / n_30m)
        start, stop = "2016-10-10", "2016-10-10T02:00"
        with mock.patch("speasy.virtual_products.expression.spz") as fake_spz:
            fake_spz.get_data.return_value = [b, n]
            results = [spz.get_data("virtual/test/ratio", start, stop), product(start, stop)]
        for result in results:
            np.testing.assert_allclose(result.values, [[5.], [10.], [15.], [15.]])
            self.assertEqual(result.name, "virtual/test/ratio")

    def test_a_lone_resample_can_be_registered(self):
        b = _make_variable([1, 3, 6, 9], step=np.timedelta64(30, "m"))
        [b_1h] = resample([self.index], "1h")
        register_virtual_product("virtual/test/b_1h", b_1h)
        with mock.patch("speasy.virtual_products.expression.spz") as fake_spz:
            fake_spz.get_data.return_value = [b]
            result = spz.get_data("virtual/test/b_1h", "2016-10-10", "2016-10-10T02:00")
        np.testing.assert_allclose(result.values, [[1.], [6.]])
        self.assertEqual(result.name, "virtual/test/b_1h")

    def test_a_lone_interpolate_can_be_registered(self):
        n_index = ParameterIndex(name="n", provider="amda", uid="n")
        b = _make_variable([1, 3, 6, 9], step=np.timedelta64(30, "m"))
        n = _make_variable([2, 4, 8])
        [n_on_b] = interpolate(self.index, [n_index])
        register_virtual_product("virtual/test/n_on_b", n_on_b)
        with mock.patch("speasy.virtual_products.expression.spz") as fake_spz:
            fake_spz.get_data.return_value = [b, n]
            result = spz.get_data("virtual/test/n_on_b", "2016-10-10", "2016-10-10T02:00")
        np.testing.assert_allclose(result.values, [[2.], [3.], [4.], [6.]])
        self.assertEqual(result.name, "virtual/test/n_on_b")


@ddt
class TestResample(unittest.TestCase):
    @data(("1s", np.timedelta64(1, "s")), ("100ms", np.timedelta64(100, "ms")))
    @unpack
    def test_string_becomes_a_timedelta(self, text, expected):
        self.assertEqual(parse_dt(text), expected)

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            parse_dt("not a duration")

    def test_repr_names_the_operand_and_the_step(self):
        leaf = Leaf(ParameterIndex(name="b", provider="cda", uid="b"))
        node = Resample(leaf, parse_dt("1s"))
        self.assertEqual(repr(node), "resample(cda/b, 1s)")

    def test_resample_gives_one_node_per_product(self):
        b = ParameterIndex(name="b", provider="cda", uid="b")
        n = ParameterIndex(name="n", provider="amda", uid="n")
        b1s, n1s = resample([b, n], "1s")
        self.assertIsInstance(b1s, Resample)
        self.assertIsInstance(n1s, Resample)
        self.assertIs(b1s.operand.index, b)
        self.assertIs(n1s.operand.index, n)
        self.assertEqual(b1s.dt, np.timedelta64(1, "s"))
        self.assertEqual(n1s.dt, np.timedelta64(1, "s"))

    def test_resample_nodes_combine_in_an_expression(self):
        b = ParameterIndex(name="b", provider="cda", uid="b")
        n = ParameterIndex(name="n", provider="amda", uid="n")
        b1s, n1s = resample([b, n], "1s")
        op = 10 * b1s / n1s
        self.assertIs(op.operands[0].operands[1], b1s)
        self.assertIs(op.operands[1], n1s)
        self.assertEqual(repr(op), "10 * resample(cda/b, 1s) / resample(amda/n, 1s)")


class TestInterpolate(unittest.TestCase):
    def test_interpolate_gives_one_node_per_product(self):
        b = ParameterIndex(name="b", provider="cda", uid="b")
        n = ParameterIndex(name="n", provider="amda", uid="n")
        [n_on_b] = interpolate(b, [n])
        self.assertIsInstance(n_on_b, Interpolate)
        self.assertIs(n_on_b.operand.index, n)
        self.assertIs(n_on_b.ref.index, b)

    def test_repr_names_the_reference_then_the_operand(self):
        b = ParameterIndex(name="b", provider="cda", uid="b")
        n = ParameterIndex(name="n", provider="amda", uid="n")
        [n_on_b] = interpolate(b, [n])
        self.assertEqual(repr(n_on_b), "interpolate(cda/b, amda/n)")

    def test_node_on_the_left_builds_an_op(self):
        b = ParameterIndex(name="b", provider="cda", uid="b")
        n = ParameterIndex(name="n", provider="amda", uid="n")
        [n_on_b] = interpolate(b, [n])
        op = n_on_b + b
        self.assertIs(op.ufunc, np.add)
        left, right = op.operands
        self.assertIs(left, n_on_b)
        self.assertIs(right.index, b)
