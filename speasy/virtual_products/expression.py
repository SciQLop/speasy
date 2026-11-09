"""Expression nodes: virtual products built from arithmetic on inventory nodes."""
from dataclasses import dataclass
from typing import Tuple, Union

import numpy as np
import pandas as pds

import speasy as spz
from speasy.core.inventory.indexes import ExpressionOperators, ParameterIndex, SpeasyIndex
from speasy.products.variable import SpeasyVariable, same_time_axis
from speasy.signal import resampling


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
class Op(ExpressionOperators):
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


@dataclass(frozen=True, eq=False)
class Resample(ExpressionOperators):
    """Directive: compute the operand on a regular time grid of step dt."""
    operand: "Node"
    dt: np.timedelta64

    def __repr__(self):
        seconds = self.dt / np.timedelta64(1, "s")
        return f"resample({self.operand!r}, {seconds:g}s)"


@dataclass(frozen=True, eq=False)
class Interpolate(ExpressionOperators):
    """Directive: compute the operand on the time axis of ref."""
    operand: "Node"
    ref: "Node"

    def __repr__(self):
        return f"interpolate({self.ref!r}, {self.operand!r})"


Node = Union[Leaf, Const, Op, Resample, Interpolate]


class TimeAxisMismatch(ValueError):
    """Raised when operands with different time axes are combined without a directive."""


def _as_node(operand):
    """Wrap one operand into a node, or None if it cannot be part of an expression."""
    if isinstance(operand, (Op, Resample, Interpolate)):
        return operand
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


def parse_dt(dt):
    """The time step as a duration: '1s' gives np.timedelta64(1, 's')."""
    return pds.Timedelta(dt).to_timedelta64()


def resample(products, dt):
    """One Resample node per product, all with the same time step."""
    step = parse_dt(dt)
    return [Resample(_as_node(product), step) for product in products]


def interpolate(ref, products):
    """One Interpolate node per product, all on the time axis of ref."""
    reference = _as_node(ref)
    return [Interpolate(_as_node(product), reference) for product in products]


def _leaf_key(index):
    """What identifies a product: two indexes with the same key are the same data."""
    return index.spz_provider(), index.spz_uid()


def _collect_all(nodes):
    """The indexes needed by several nodes, without duplicates, in reading order."""
    indexes = {}
    for node in nodes:
        for index in collect(node):
            indexes.setdefault(_leaf_key(index), index)
    return list(indexes.values())


def collect(node):
    """The indexes of the products an expression needs, in reading order."""
    if isinstance(node, Leaf):
        return [node.index]
    if isinstance(node, Const):
        return []
    if isinstance(node, Resample):
        return collect(node.operand)
    if isinstance(node, Interpolate):
        return _collect_all((node.ref, node.operand))
    if isinstance(node, Op):
        return _collect_all(node.operands)
    raise TypeError(f"Cannot collect {node!r}: not an expression node")


def fetch(indexes, start, stop):
    """The data of all the given products, in the same order, from one get_data call."""
    return spz.get_data(indexes, start, stop)


def bind(indexes, variables):
    """Map each product's key to its data, or None if a product has no data."""
    if any(variable is None for variable in variables):
        return None
    return {_leaf_key(index): variable for index, variable in zip(indexes, variables)}


def _cadence(variable):
    """The time between two samples, as a readable string: '16 Hz' or '4.5 s'."""
    seconds = np.median(np.diff(variable.time) / np.timedelta64(1, "s"))
    if seconds < 1:
        return f"{1 / seconds:g} Hz"
    return f"{seconds:g} s"


def _time_axis_mismatch_message(node, data):
    """Name each product of the expression, its cadence and size, and the directive to add."""
    indexes = collect(node)
    names = [f"'{Leaf(index)!r}'" for index in indexes]
    width = max(len(name) for name in names)
    products = []
    for name, index in zip(names, indexes):
        variable = data[_leaf_key(index)]
        products.append(f"  {name:<{width}}  ({_cadence(variable)}, {len(variable.time)} points)\n")
    return (f"cannot combine\n{''.join(products)}in expression '{node!r}'.\n"
            "Add an explicit directive, e.g.:\n"
            '  b, n = speasy.virtual_products.resample([B, N], "1s")')


def _interpolate_checked(ref, variable, node):
    """Interpolate a variable on ref, refusing more than two dimensions with a clear error."""
    ndim = variable.values.ndim
    if ndim > 2:
        raise ValueError(f"Cannot compute {node!r}: interpolating a {ndim}-D variable is not supported")
    return resampling.interpolate(ref, variable)


def walk(node, data, start, stop):
    """Compute an expression tree from the already fetched data."""
    if isinstance(node, Leaf):
        return data[_leaf_key(node.index)]
    if isinstance(node, Const):
        return node.value
    if isinstance(node, Resample):
        variable = walk(node.operand, data, start, stop)
        grid = resampling.generate_time_vector(start, stop, node.dt)
        return _interpolate_checked(grid, variable, node)
    if isinstance(node, Interpolate):
        reference = walk(node.ref, data, start, stop)
        variable = walk(node.operand, data, start, stop)
        return _interpolate_checked(reference, variable, node)
    if isinstance(node, Op):
        operands = [walk(operand, data, start, stop) for operand in node.operands]
        variables = [operand for operand in operands if isinstance(operand, SpeasyVariable)]
        if not same_time_axis(variables):
            raise TimeAxisMismatch(_time_axis_mismatch_message(node, data))
        return node.ufunc(*operands)
    raise TypeError(f"Cannot walk {node!r}: not an expression node")


def finalise(result, node):
    """Name the result after the expression that computed it."""
    return result.copy(name=repr(node))


def evaluate(node, start, stop):
    """Compute an expression tree over [start, stop]: fetch its products, then walk it."""
    indexes = collect(node)
    variables = fetch(indexes, start, stop)
    data = bind(indexes, variables)
    if data is None:
        return None
    result = walk(node, data, start, stop)
    named = finalise(result, node)
    return named
