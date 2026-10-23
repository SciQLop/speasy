"""Turns a SpeasyVariable dictionary into plain data and back, and stores plain data only."""
from datetime import datetime

import msgspec
import numpy as np

from speasy.core.proxy import blosc_arrays, unblosc_arrays


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
