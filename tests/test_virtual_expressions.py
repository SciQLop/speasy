import dataclasses
import unittest

import numpy as np

from speasy.core.inventory.indexes import ParameterIndex
from speasy.virtual_products.expression import Const, Leaf, Op


class TestNodes(unittest.TestCase):
    def setUp(self):
        self.index = ParameterIndex(name="b", provider="cda", uid="b")
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
