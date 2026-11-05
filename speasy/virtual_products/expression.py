"""Expression nodes: virtual products built from arithmetic on inventory nodes."""
from dataclasses import dataclass
from typing import Tuple, Union

import numpy as np

import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex


@dataclass(frozen=True, eq=False)
class Leaf:
    """A product to fetch: an inventory node or a 'provider/uid' path string."""
    index: Union[SpeasyIndex, str]

    def __repr__(self):
        if isinstance(self.index, str):
            return self.index
        return f"{self.index.spz_provider()}/{self.index.spz_uid()}"


@dataclass(frozen=True, eq=False)
class Const:
    """A Python scalar, e.g. the 10 in 10 * B."""
    value: Union[int, float]

    def __repr__(self):
        return repr(self.value)


_BINARY_SYMBOLS = {
    np.add: "+",
    np.subtract: "-",
    np.multiply: "*",
    np.divide: "/",
    np.power: "**",
}

_PREFIX_SYMBOLS = {np.negative: "-"}

_CALL_NAMES = {np.absolute: "abs"}

_PRECEDENCE_LEVEL = {
    np.add: 1,
    np.subtract: 1,
    np.multiply: 2,
    np.divide: 2,
    np.negative: 3,
    np.power: 4,
}


def _precedence(node):
    """How tightly a node binds; leaves, constants and calls like abs(x) bind tightest."""
    if isinstance(node, Op) and node.ufunc in _PRECEDENCE_LEVEL:
        return _PRECEDENCE_LEVEL[node.ufunc]
    return max(_PRECEDENCE_LEVEL.values()) + 1


def _operand_repr(node, precedence, parenthesize_equal):
    """repr of an operand, parenthesized when it binds less tightly than its operator,
    or exactly as tightly when parenthesize_equal is set."""
    text = repr(node)
    weaker = _precedence(node) < precedence
    equal = parenthesize_equal and _precedence(node) == precedence
    return f"({text})" if weaker or equal else text


@dataclass(frozen=True, eq=False)
class Op:
    """Elementwise application of a numpy ufunc to its operands."""
    ufunc: np.ufunc
    operands: Tuple["Node", ...]

    def __repr__(self):
        if self.ufunc in _CALL_NAMES:
            (operand,) = self.operands
            return f"{_CALL_NAMES[self.ufunc]}({operand!r})"
        precedence = _PRECEDENCE_LEVEL[self.ufunc]
        if self.ufunc in _PREFIX_SYMBOLS:
            (operand,) = self.operands
            text = _operand_repr(operand, precedence, parenthesize_equal=False)
            return f"{_PREFIX_SYMBOLS[self.ufunc]}{text}"
        # ** groups right to left: a ** b ** c means a ** (b ** c)
        right_associative = self.ufunc is np.power
        left_operand, right_operand = self.operands
        left = _operand_repr(left_operand, precedence, parenthesize_equal=right_associative)
        right = _operand_repr(right_operand, precedence, parenthesize_equal=not right_associative)
        return f"{left} {_BINARY_SYMBOLS[self.ufunc]} {right}"


Node = Union[Leaf, Const, Op]


def _as_node(operand):
    """Wrap one operand into a node, or None if it cannot be part of an expression."""
    if isinstance(operand, ParameterIndex):
        return Leaf(operand)
    if isinstance(operand, (int, float)):
        return Const(operand)
    return None


def make_op(ufunc, left, right):
    """Op for `left <ufunc> right`, or NotImplemented if an operand is not supported."""
    left_node, right_node = _as_node(left), _as_node(right)
    if left_node is None or right_node is None:
        return NotImplemented
    return Op(ufunc, (left_node, right_node))


def _leaf_key(index):
    """What identifies a product: two indexes with the same key are the same data."""
    return index.spz_provider(), index.spz_uid()


def collect(node):
    """The indexes of the products an expression needs, in reading order."""
    if isinstance(node, Leaf):
        return [node.index]
    if isinstance(node, Const):
        return []
    if isinstance(node, Op):
        indexes = {}
        for operand in node.operands:
            for index in collect(operand):
                indexes.setdefault(_leaf_key(index), index)
        return list(indexes.values())
    raise TypeError(f"Cannot collect {node!r}: not an expression node")


def fetch(indexes, start, stop):
    """The data of all the given products, in the same order, from one get_data call."""
    return spz.get_data(indexes, start, stop)


def bind(indexes, variables):
    """Map each product's key to its data."""
    return {_leaf_key(index): variable for index, variable in zip(indexes, variables)}


def evaluate(node, start, stop):
    """Compute an expression tree over [start, stop]: fetch the leaves, apply the ufuncs."""
    if isinstance(node, Leaf):
        return spz.get_data(node.index, start, stop)
    if isinstance(node, Const):
        return node.value
    if isinstance(node, Op):
        operands = [evaluate(operand, start, stop) for operand in node.operands]
        return node.ufunc(*operands)
    raise TypeError(f"Cannot evaluate {node!r}: not an expression node")
