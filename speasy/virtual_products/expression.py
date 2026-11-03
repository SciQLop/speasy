"""Expression nodes: virtual products built from arithmetic on inventory nodes."""
from dataclasses import dataclass
from typing import Tuple, Union

import numpy as np

from speasy.core.inventory.indexes import SpeasyIndex


@dataclass(frozen=True, eq=False)
class Leaf:
    """A product to fetch: an inventory node or a 'provider/uid' path string."""
    index: Union[SpeasyIndex, str]


@dataclass(frozen=True, eq=False)
class Const:
    """A Python scalar, e.g. the 10 in 10 * B."""
    value: Union[int, float]


@dataclass(frozen=True, eq=False)
class Op:
    """Elementwise application of a numpy ufunc to its operands."""
    ufunc: np.ufunc
    operands: Tuple["Node", ...]


Node = Union[Leaf, Const, Op]
