"""Turns Speasy products into plain data and back, and stores plain data only."""
from datetime import datetime
from typing import Optional

import msgspec
import numpy as np

from speasy.core.proxy import blosc_arrays, unblosc_arrays
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import SpeasyIndex, from_dict as inventory_from_dict, to_dict as inventory_to_dict
from speasy.products import Catalog, Dataset, Event, SpeasyVariable, TimeTable
from speasy.products.variable import from_dictionary


class Serializer:
    """msgpack with no extension: writing anything but plain data raises, and reading never builds an object.

    pysciqlop-cache's own msgspec serializer imports any class an "object" extension names, and an index can come
    from someone else (import_data)."""
    name = "speasy-data-index"

    def dumps(self, value) -> bytes:
        return msgspec.msgpack.encode(value)

    def loads(self, data):
        return msgspec.msgpack.decode(data)


class NotStorable(TypeError):
    """A value or product kind a data index doesn't know how to store; ``product`` is the product it came with."""

    def __init__(self, message: str, product=None):
        super().__init__(message)
        self.product = product


def _array(array: np.ndarray, path: str):
    marker = blosc_arrays(array)
    if marker is not array:
        return marker
    # empty and non-numeric arrays, which blosc doesn't take; an object array keeps its elements, if storable
    elements = [to_storable(v, path) for v in array.ravel().tolist()] if array.dtype.kind == 'O' else array.tolist()
    return {"__array__": elements, "dtype": array.dtype.str, "shape": list(array.shape)}


_PLAIN = (type(None), bool, int, float, str, bytes)


def to_storable(obj, path: str = ""):
    """``obj`` as plain data msgpack holds without losing its type: numpy arrays become blosc or list markers, numpy
    scalars Python ones, and datetimes, tuples, sets, complex numbers and inventory nodes get a marker. Raises
    NotStorable, naming the field, for anything else."""
    if isinstance(obj, np.datetime64):
        return {"__datetime64__": str(obj)}
    if isinstance(obj, np.generic):  # before plain types: np.float64 is a float msgpack still refuses
        return to_storable(obj.item(), path)
    if isinstance(obj, _PLAIN):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_storable(v, f"{path}/{k}") for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_storable(v, path) for v in obj]
    if isinstance(obj, np.ndarray):
        return _array(obj, path.lstrip('/'))
    # msgpack turns a naive datetime into a str, and a tuple or a set into a list
    if isinstance(obj, datetime):
        return {"__datetime__": obj.isoformat()}
    if isinstance(obj, tuple):
        return {"__tuple__": [to_storable(v, path) for v in obj]}
    if isinstance(obj, (set, frozenset)):
        return {"__set__": [to_storable(v, path) for v in obj]}
    if isinstance(obj, complex):
        return {"__complex__": [obj.real, obj.imag]}
    if isinstance(obj, SpeasyIndex):
        # e.g. AMDA's catalogs hold inventory nodes in their meta
        return {"__speasy_index__": to_storable(inventory_to_dict(obj, version=2), path)}
    raise NotStorable(f"{path.lstrip('/')}: can't store a {type(obj).__name__} ({obj!r}) in a data index")


def _object_array(marker: dict) -> np.ndarray:
    array = np.empty(len(marker["__array__"]), dtype=object)
    array[:] = [from_storable(v) for v in marker["__array__"]]
    return array.reshape(marker["shape"])


_MARKERS = {
    "__blosc__": unblosc_arrays,
    "__array__": lambda m: _object_array(m) if m["dtype"] == "|O" else np.array(m["__array__"], dtype=m["dtype"]),
    "__datetime64__": lambda m: np.datetime64(m["__datetime64__"]),
    "__datetime__": lambda m: datetime.fromisoformat(m["__datetime__"]),
    "__tuple__": lambda m: tuple(from_storable(v) for v in m["__tuple__"]),
    "__set__": lambda m: set(from_storable(v) for v in m["__set__"]),
    "__complex__": lambda m: complex(*m["__complex__"]),
    # inventory_from_dict only builds Speasy's own index classes: nothing an archive names is imported
    "__speasy_index__": lambda m: inventory_from_dict(from_storable(m["__speasy_index__"]), version=2),
}


def from_storable(obj):
    if isinstance(obj, dict):
        marker = next((key for key in _MARKERS if key in obj), None)
        if marker is not None:
            return _MARKERS[marker](obj)
        return {k: from_storable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [from_storable(v) for v in obj]
    return obj


def _ranges(ranges) -> list:
    return [[r.start_time.isoformat(), r.stop_time.isoformat()] for r in ranges]


def _variable(variable: SpeasyVariable, path: str = "variable") -> dict:
    return to_storable(variable.to_dictionary(), path)


def store_product(product) -> Optional[dict]:
    """Any product speasy.get_data gives, as plain data with its kind; None stays None."""
    if product is None:
        return None
    if isinstance(product, SpeasyVariable):
        return {"kind": "variable", "variable": _variable(product)}
    if isinstance(product, Dataset):
        return {"kind": "dataset", "name": product.name, "meta": to_storable(product.meta),
                "variables": {name: _variable(v, f"variables/{name}") for name, v in product.variables.items()}}
    if isinstance(product, TimeTable):
        return {"kind": "timetable", "name": product.name, "meta": to_storable(product.meta), "ranges": _ranges(product)}
    if isinstance(product, Catalog):
        return {"kind": "catalog", "name": product.name, "meta": to_storable(product.meta),
                "events": [[*_ranges([e])[0], to_storable(e.meta)] for e in product]}
    raise NotStorable(f"a data index can't store a {type(product).__name__}", product)


def _time(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


_LOADERS = {
    "variable": lambda s: from_dictionary(from_storable(s["variable"])),
    "dataset": lambda s: Dataset(s["name"], {name: from_dictionary(from_storable(v)) for name, v in s["variables"].items()},
                                 from_storable(s["meta"])),
    "timetable": lambda s: TimeTable(s["name"], from_storable(s["meta"]),
                                     [DateTimeRange(_time(start), _time(stop)) for start, stop in s["ranges"]]),
    "catalog": lambda s: Catalog(s["name"], from_storable(s["meta"]),
                                 [Event(_time(start), _time(stop), from_storable(meta)) for start, stop, meta in s["events"]]),
}


def load_product(stored: Optional[dict]):
    return None if stored is None else _LOADERS[stored["kind"]](stored)
