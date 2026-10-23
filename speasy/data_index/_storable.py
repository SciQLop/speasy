"""Turns Speasy products into plain data and back, and stores plain data only."""
from datetime import datetime
from typing import Optional

import msgspec
import numpy as np

from speasy.core.proxy import blosc_arrays, unblosc_arrays
from speasy.core.datetime_range import DateTimeRange
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


def _array(array: np.ndarray, path: str):
    if array.dtype.kind == 'O':
        raise ValueError(f"{path}: can't store an array of Python objects ({array.dtype}) in a data index")
    marker = blosc_arrays(array)
    if marker is not array:
        return marker
    # empty and non-numeric arrays, which blosc doesn't take
    return {"__array__": array.tolist(), "dtype": array.dtype.str}


def to_storable(obj, path: str = ""):
    """``obj`` as plain data: numpy arrays become blosc or list markers, numpy scalars Python ones, datetimes ISO
    strings, tuples lists and dict keys str. Raises ValueError, naming the field, for what can't be stored."""
    if isinstance(obj, dict):
        return {str(k): to_storable(v, f"{path}/{k}") for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_storable(v, path) for v in obj]
    if isinstance(obj, np.ndarray):
        return _array(obj, path.lstrip('/'))
    if isinstance(obj, np.datetime64):
        return str(obj)
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def from_storable(obj):
    if isinstance(obj, dict):
        if "__blosc__" in obj:
            return unblosc_arrays(obj)
        if "__array__" in obj:
            return np.array(obj["__array__"], dtype=obj["dtype"])
        return {k: from_storable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [from_storable(v) for v in obj]
    return obj


class NotStorable(TypeError):
    """A product kind a data index doesn't know how to store."""


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
    raise NotStorable(f"a data index can't store a {type(product).__name__}")


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
