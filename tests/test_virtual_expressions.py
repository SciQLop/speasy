import dataclasses
import operator
import unittest

import numpy as np
from ddt import data, ddt, unpack

from speasy.core.inventory.indexes import ParameterIndex
from speasy.virtual_products.expression import Const, Leaf, Op


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
