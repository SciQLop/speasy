import copy
import dataclasses
import operator
import unittest
from unittest import mock

import numpy as np
from ddt import data, ddt, unpack

import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex
from speasy.virtual_products import register_virtual_product
from speasy.virtual_products.expression import Const, Leaf, Op, bind, collect, evaluate, fetch, walk
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis
from tests.test_virtual_products import _reset_registry

_T0 = np.datetime64("2016-10-10T00:00", "ns")


def _make_variable(values):
    """Synthetic SpeasyVariable: the given values, one point per hour from _T0."""
    values = np.asarray(values, dtype=float)
    time = _T0 + np.arange(len(values)) * np.timedelta64(1, "h")
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                          values=DataContainer(values=values, meta=None),
                          columns=["Values"])


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
        result = walk(10 * index, {("cda", "b"): b})
        np.testing.assert_array_equal(result.values, [[10.], [20.], [30.]])
        np.testing.assert_array_equal(result.time, b.time)


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
