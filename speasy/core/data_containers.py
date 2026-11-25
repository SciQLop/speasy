import logging
from copy import deepcopy, copy
from datetime import datetime
from sys import getsizeof
from typing import Dict, List, Optional, Protocol, TypeVar, Union, Any

import astropy.units
import numpy as np

from .time import make_utc_datetime64

log = logging.getLogger(__name__)


def scalar_meta(meta: Dict, key: str) -> Any:
    """Returns a metadata entry, unwrapped from the single-element list CDF attributes arrive in."""
    value = meta.get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _fits_in(fillval, dtype: np.dtype) -> bool:
    if np.isnan(fillval):
        return True  # NaN compares False against everything, a range check included
    info = np.iinfo(dtype) if np.issubdtype(dtype, np.integer) else np.finfo(dtype)
    return bool(info.min <= fillval <= info.max)


def fill_value_mask(values: np.ndarray, meta: Dict) -> Optional[np.ndarray]:
    """Returns a boolean mask of the entries equal to the ISTP FILLVAL, or None when no mask can
    be computed at all.

    None means undecidable, not "nothing matched": either FILLVAL is absent, or it is a string
    while the data is numeric, which warns. That second case is a real ISTP pattern rather than a
    hypothetical -- CDAWeb mis-declares some numeric variables' FILLVAL with a TT2000/EPOCH
    attribute type, which the data codec stringifies (e.g. ela_att_solution_date), and there is no
    reliable way to recover the intended numeric sentinel from that mismatch.

    A NaN FILLVAL needs no special case: NaN != NaN, so it simply matches nothing, which is right
    because such data already carries NaN where it means fill.
    """
    fillval = scalar_meta(meta, "FILLVAL")
    if fillval is None:
        return None
    if not np.issubdtype(values.dtype, np.number):
        return values == fillval
    if isinstance(fillval, str):
        log.warning(
            f"FILLVAL {fillval!r} is a string but the data is numeric ({values.dtype}); "
            "skipping fill-value masking."
        )
        return None
    if not _fits_in(fillval, values.dtype):
        log.warning(
            f"FILLVAL {fillval!r} is outside the range of the data type ({values.dtype}), so no "
            "sample can ever equal it; skipping fill-value masking."
        )
        return None
    return values == fillval


def _name(input_p: Any) -> str:
    if hasattr(input_p, "name"):
        return input_p.name
    if isinstance(input_p, (list, tuple)):
        return f"[{', '.join(map(_name, input_p))}]"
    return str(input_p)


def np_build_result_name(func, *args, **kwargs):
    return f"{func.__name__}({', '.join(map(_name, args))}{', ' * bool(kwargs)}{', '.join([f'{k}={_name(v)}' for k, v in kwargs.items()])})"

def _values(input_p: Any) -> Any:
    if hasattr(input_p, "values"):
        return input_p.values
    return input_p

def _data_container(input_p: Any) -> 'DataContainer' or None:
    if hasattr(input_p, "data_container"):
        return input_p.data_container
    if isinstance(input_p, DataContainer):
        return input_p
    return input_p

def _to_index(key, time):
    if key is None:
        return None
    if isinstance(key, (int, np.integer)):
        return key
    if isinstance(key, float):
        # kept apart from make_utc_datetime64, which rounds epochs to microseconds
        return np.searchsorted(time, np.datetime64(int(key * 1e9), 'ns'), side='left')
    if isinstance(key, (str, datetime, np.datetime64)):
        return np.searchsorted(time, make_utc_datetime64(key).astype('datetime64[ns]'), side='left')
    raise TypeError(f"Can't slice a SpeasyVariable with {key!r}: use row indexes, or times as a string, "
                    f"a datetime, a numpy datetime64 or seconds since 1970")


T = TypeVar("T")  # keep until we drop python 3.11 support


def numpy_supported(cls):

    def __ge__(self, other:Any) -> Union[bool, np.ndarray]:
        return np.greater_equal(self, other)

    def __gt__(self, other:Any) -> Union[bool, np.ndarray]:
        return np.greater(self, other)

    def __le__(self, other:Any) -> Union[bool, np.ndarray]:
        return np.less_equal(self, other)

    def __lt__(self, other:Any) -> Union[bool, np.ndarray]:
        return np.less(self, other)

    def __add__(self, other:Any) -> 'DataContainer':
        return np.add(self, other)

    def __radd__(self, other:Any) -> 'DataContainer':
        return np.add(other, self)

    def __sub__(self, other:Any) -> 'DataContainer':
        return np.subtract(self, other)

    def __rsub__(self, other:Any) -> 'DataContainer':
        return np.subtract(other, self)

    def __mul__(self, other:Any) -> 'DataContainer':
        return np.multiply(self, other)

    def __rmul__(self, other:Any) -> 'DataContainer':
        return np.multiply(other, self)

    def __truediv__(self, other:Any) -> 'DataContainer':
        return np.divide(self, other)

    def __rtruediv__(self, other:Any) -> 'DataContainer':
        return np.divide(other, self)

    def __pow__(self, other:Any) -> 'DataContainer':
        return np.power(self, other)

    cls.__ge__ = __ge__
    cls.__gt__ = __gt__
    cls.__le__ = __le__
    cls.__lt__ = __lt__
    cls.__add__ = __add__
    cls.__radd__ = __radd__
    cls.__sub__ = __sub__
    cls.__rsub__ = __rsub__
    cls.__mul__ = __mul__
    cls.__rmul__ = __rmul__
    cls.__truediv__ = __truediv__
    cls.__rtruediv__ = __rtruediv__
    cls.__pow__ = __pow__

    return cls


class DataContainerProtocol(Protocol[T]):
    def select(self, indices, inplace=False) -> T:
        ...

    def to_dictionary(self, array_to_list=False) -> Dict[str, object]:
        ...

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Union[str, Dict[str, str], List]], dtype=np.float64) -> T:
        ...

    @staticmethod
    def reserve_like(other: T, length: int = 0) -> T:
        ...

    def __getitem__(self, key) -> T:
        ...

    def __setitem__(self, k, v: Union[T, float, int]):
        ...

    def __len__(self) -> int:
        ...

    def __eq__(self, other: Union[T, float, int]) -> Union[bool, np.ndarray]:
        ...

    @property
    def unit(self) -> str:
        ...

    @property
    def is_time_dependent(self) -> bool:
        ...

    @property
    def values(self) -> np.array:
        ...

    @property
    def shape(self):
        ...

    @property
    def name(self) -> str:
        ...

    @property
    def nbytes(self) -> int:
        ...

    @property
    def dtype(self)-> np.dtype:
        ...

    def view(self, index_range: Union[slice, np.ndarray]) -> T:
        ...

    def astype(self, dtype) -> T:
        ...




@numpy_supported
class DataContainer(DataContainerProtocol['DataContainer']):
    __slots__ = ['__values', '__name', '__meta', '__is_time_dependent']
    __LIKE_NP_FUNCTIONS__ = {'zeros_like', 'empty_like', 'ones_like'}

    def __init__(self, values: np.array, meta: Dict = None, name: str = None, is_time_dependent: bool = True):
        if not isinstance(values, np.ndarray):
            raise ValueError(f"values must be a numpy array, got {type(values)}")
        self.__values = values
        self.__is_time_dependent = is_time_dependent
        self.__name = name or ""
        self.__meta = meta or {}

    def reshape(self, new_shape) -> "DataContainer":
        self.__values = self.__values.reshape(new_shape)
        return self

    def select(self, indices, inplace=False) -> "DataContainer":
        if inplace:
            res = self
        else:
            res = deepcopy(self)
        res.__values = res.__values[indices]

    @property
    def is_time_dependent(self) -> bool:
        return self.__is_time_dependent

    @property
    def values(self) -> np.array:
        return self.__values

    @property
    def shape(self):
        return self.__values.shape

    @property
    def ndim(self):
        return self.__values.ndim

    @property
    def dtype(self):
        return self.__values.dtype

    def astype(self, dtype) -> "DataContainer":
        return DataContainer(values=self.__values.astype(dtype), meta=copy(self.__meta), name=self.__name,
                             is_time_dependent=self.__is_time_dependent)

    @property
    def unit(self) -> str:
        return self.__meta.get('UNITS')

    @property
    def nbytes(self) -> int:
        return self.__values.nbytes + getsizeof(self.__meta) + getsizeof(self.__name)

    def view(self, index_range: Union[slice, np.ndarray]):
        return DataContainer(name=self.__name, meta=self.__meta, values=self.__values[index_range],
                             is_time_dependent=self.__is_time_dependent)

    def unit_applied(self, unit: str or None = None) -> "DataContainer":
        try:
            u = astropy.units.Unit(unit or self.unit)
        except (ValueError, KeyError, TypeError):
            u = astropy.units.Unit("")

        return DataContainer(values=self.__values * u, meta=self.__meta, name=self.__name,
                             is_time_dependent=self.__is_time_dependent)

    def to_dictionary(self, array_to_list=False) -> Dict[str, object]:
        return {
            "values": self.__values.tolist() if array_to_list else self.__values.copy(),
            "meta": self.__meta.copy(),
            "name": self.__name,
            "is_time_dependent": self.is_time_dependent,
            "values_type": str(self.__values.dtype)
        }

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Union[str, Dict[str, str], List]], dtype=np.float64) -> "DataContainer":
        try:
            return DataContainer(
                values=np.asarray(dictionary["values"], dtype=dictionary.get("values_type", dtype)),
                meta=dictionary["meta"],
                name=dictionary["name"],
                is_time_dependent=dictionary["is_time_dependent"]
            )
        except ValueError:
            return DataContainer(
                values=np.asarray(dictionary["values"]), meta=dictionary["meta"],
                name=dictionary["name"],
                is_time_dependent=dictionary["is_time_dependent"]
            )

    @staticmethod
    def reserve_like(other: 'DataContainer', length: int = 0) -> 'DataContainer':
        return DataContainer(name=other.__name, meta=other.__meta,
                             values=np.empty(
                                 (length,) + other.shape[1:], dtype=other.__values.dtype),
                             is_time_dependent=other.__is_time_dependent
                             )

    @staticmethod
    def zeros_like(other: 'DataContainer') -> 'DataContainer':
        return DataContainer(name=other.__name, meta=other.__meta,
                             values=np.zeros_like(other.__values, dtype=other.__values.dtype),
                             is_time_dependent=other.__is_time_dependent
                             )

    @staticmethod
    def ones_like(other: 'DataContainer') -> 'DataContainer':
        return DataContainer(name=other.__name, meta=other.__meta,
                             values=np.ones_like(other.__values, dtype=other.__values.dtype),
                             is_time_dependent=other.__is_time_dependent
                             )

    @staticmethod
    def empty_like(other: 'DataContainer') -> 'DataContainer':
        return DataContainer(name=other.__name, meta=other.__meta,
                             values=np.empty_like(other.__values, dtype=other.__values.dtype),
                             is_time_dependent=other.__is_time_dependent
                             )

    def copy(self, name=None):
        return DataContainer(name=name or self.__name, meta=deepcopy(self.__meta), values=deepcopy(self.__values),
                             is_time_dependent=self.__is_time_dependent)

    def __len__(self):
        return len(self.__values)

    def __getitem__(self, key):
        return self.view(key)

    def __setitem__(self, k, v: Union['DataContainer', float, int]):
        if type(v) is DataContainer:
            self.__values[k] = v.__values
        else:
            self.__values[k] = v

    def __eq__(self, other: Union['DataContainer', float, int]) -> Union[bool, np.ndarray]:
        if type(other) is DataContainer:
            return self.__meta == other.__meta and \
                self.__name == other.__name and \
                self.is_time_dependent == other.is_time_dependent and \
                np.all(self.__values.shape == other.__values.shape) and \
                np.array_equal(self.__values, other.__values, equal_nan=np.issubdtype(self.__values.dtype, np.floating))
        else:
            return self.__values.__eq__(other)

    def __array_function__(self, func, types, args, kwargs):
        if func.__name__ in DataContainer.__LIKE_NP_FUNCTIONS__:
            return DataContainer.__dict__[func.__name__].__func__(self)
        if 'out' in kwargs:
            raise ValueError("out parameter is not supported")
        f_args = [_values(arg) for arg in args]
        f_kwargs = {name: _values(value) for name, value in kwargs.items()}

        res = func(*f_args, **f_kwargs)

        if np.isscalar(res):
            return res
        else:
            return DataContainer(values=res, meta=deepcopy(self.__meta), name=np_build_result_name(func, *args, **kwargs),
                                 is_time_dependent=self.__is_time_dependent)

    def __array_ufunc__(self, ufunc, method, *inputs, out: 'DataContainer' or None = None, **kwargs):
        if out is not None:
            _out = out[0].values
        else:
            _out = None

        res = ufunc(*list(map(_values, inputs)), **{name: _values(value) for name, value in kwargs}, out=_out)

        if _out is not None:
            return _out
        else:
            return DataContainer(values=res, meta=deepcopy(self.__meta), name=self.__name,
                                 is_time_dependent=self.__is_time_dependent)

    @property
    def meta(self):
        return self.__meta

    @property
    def name(self):
        return self.__name


def _checked_delta(delta: Optional[np.ndarray], values: np.ndarray, which: str, name: str) -> Optional[np.ndarray]:
    if delta is None:
        return None
    delta = np.asarray(delta)
    if delta.shape != values.shape:
        raise ValueError(f"{which} of axis {name!r} has shape {delta.shape}, it must have the shape of the axis "
                         f"values {values.shape}")
    return delta


def _same_or_both_none(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return np.array_equal(a, b, equal_nan=True)


class VariableAxis(DataContainerProtocol['VariableAxis']):
    """An axis of a SpeasyVariable. ``delta_plus`` and ``delta_minus``, when known, are the distances from each
    value to its bin's upper and lower edges (ISTP DELTA_PLUS_VAR / DELTA_MINUS_VAR), with the values' shape."""
    __slots__ = ['__data', '__delta_plus', '__delta_minus']
    __LIKE_NP_FUNCTIONS__ = {'zeros_like', 'empty_like', 'ones_like'}

    def __init__(self, values: np.array = None, meta: Dict = None, name: str = "", is_time_dependent: bool = False,
                 data: DataContainer = None, delta_plus: Optional[np.ndarray] = None,
                 delta_minus: Optional[np.ndarray] = None):
        if data is not None:
            self.__data = data
        else:
            self.__data = DataContainer(
                values=values, name=name, meta=meta, is_time_dependent=is_time_dependent)
        self.__delta_plus = _checked_delta(delta_plus, self.__data.values, 'delta_plus', self.__data.name)
        self.__delta_minus = _checked_delta(delta_minus, self.__data.values, 'delta_minus', self.__data.name)

    def __setstate__(self, state):
        # axes pickled before deltas existed only carry __data
        self.__delta_plus = self.__delta_minus = None
        for part in state if isinstance(state, tuple) else (state,):
            for name, value in (part or {}).items():
                setattr(self, name, value)

    def __deltas(self):
        return self.__delta_plus, self.__delta_minus

    def __with_deltas(self, data: DataContainer, transform) -> 'VariableAxis':
        plus, minus = self.__deltas()
        return VariableAxis(data=data, delta_plus=None if plus is None else transform(plus),
                            delta_minus=None if minus is None else transform(minus))

    @property
    def delta_plus(self) -> Optional[np.ndarray]:
        return self.__deltas()[0]

    @property
    def delta_minus(self) -> Optional[np.ndarray]:
        return self.__deltas()[1]

    def zeros_like(self) -> "VariableAxis":
        return self.__with_deltas(DataContainer.zeros_like(self.__data), np.copy)

    def ones_like(self) -> "VariableAxis":
        return self.__with_deltas(DataContainer.ones_like(self.__data), np.copy)

    def empty_like(self) -> "VariableAxis":
        return self.__with_deltas(DataContainer.empty_like(self.__data), np.copy)

    def to_dictionary(self, array_to_list=False) -> Dict[str, object]:
        d = self.__data.to_dictionary(array_to_list=array_to_list)
        d.update({"type": "VariableAxis"})
        for key, delta in zip(("delta_plus", "delta_minus"), self.__deltas()):
            if delta is not None:
                d[key] = delta.tolist() if array_to_list else delta.copy()
        return d

    def select(self, indices, inplace=False) -> "VariableAxis":
        data = deepcopy(self.__data)
        data.select(indices, inplace=True)
        selected = self.__with_deltas(data, lambda delta: delta[indices])
        if not inplace:
            return selected
        self.__data = selected.__data
        self.__delta_plus, self.__delta_minus = selected.__deltas()
        return self

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Union[str, Dict[str, str], List]], time=None) -> "VariableAxis":
        assert dictionary['type'] == "VariableAxis"
        deltas = {key: np.asarray(dictionary[key], dtype=float) for key in ("delta_plus", "delta_minus")
                  if dictionary.get(key) is not None}
        return VariableAxis(data=DataContainer.from_dictionary(dictionary), **deltas)

    @staticmethod
    def reserve_like(other: 'VariableAxis', length: int = 0) -> 'VariableAxis':
        return other.__with_deltas(DataContainer.reserve_like(other.__data, length),
                                   lambda delta: np.empty((length,) + delta.shape[1:], dtype=delta.dtype)
                                   if other.is_time_dependent else delta.copy())

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(slice(_to_index(key.start, self.__data.values), _to_index(key.stop, self.__data.values)))
        else:
            return self.view(key)

    def __setitem__(self, k, v: Union['VariableAxis', float, int]):
        if type(v) is VariableAxis:
            self.__data[k] = v.__data
            for mine, theirs in zip(self.__deltas(), v.__deltas()):
                if mine is not None and theirs is not None:
                    mine[k] = theirs
        else:
            self.__data[k] = v

    def __len__(self):
        return len(self.__data)

    def view(self, index_range: Union[slice, np.ndarray]) -> 'VariableAxis':
        return self.__with_deltas(self.__data[index_range], lambda delta: delta[index_range])

    def __eq__(self, other: 'VariableAxis') -> bool:
        return type(other) is VariableAxis and self.__data == other.__data and \
            all(map(_same_or_both_none, self.__deltas(), other.__deltas()))

    def __array_function__(self, func, types, args, kwargs):
        if func.__name__ in VariableAxis.__LIKE_NP_FUNCTIONS__:
            return VariableAxis.__dict__[func.__name__].__func__(self)
        if 'out' in kwargs:
            raise ValueError("out parameter is not supported")
        f_args = [_data_container(arg) for arg in args]
        f_kwargs = {name: _data_container(value) for name, value in kwargs.items()}
        r = func(*f_args, **f_kwargs)
        if isinstance(r, DataContainer):
            return VariableAxis(data=r)
        return r

    def __array_ufunc__(self, ufunc, method, *inputs, out: 'VariableAxis' or None = None, **kwargs):
        if out is not None:
            _out = out[0].__data
        else:
            _out = None

        res = self.__data.__array_ufunc__(ufunc, method, *inputs, out=_out, **kwargs)

        if _out is not None:
            return out[0]
        if isinstance(res, DataContainer):
            return VariableAxis(data=res)
        return res

    def astype(self, dtype) -> 'VariableAxis':
        return self.__with_deltas(self.__data.astype(dtype), np.copy)

    @property
    def unit(self) -> str:
        return self.__data.unit

    @property
    def is_time_dependent(self) -> bool:
        return self.__data.is_time_dependent

    @property
    def values(self) -> np.array:
        return self.__data.values

    @property
    def data_container(self) -> DataContainer:
        return self.__data

    @property
    def shape(self):
        return self.__data.shape

    @property
    def name(self) -> str:
        return self.__data.name

    @property
    def nbytes(self) -> int:
        return self.__data.nbytes

    @property
    def meta(self) -> Dict:
        return self.__data.meta

    @property
    def dtype(self)-> np.dtype:
        return self.__data.dtype


@numpy_supported
class VariableTimeAxis(DataContainerProtocol['VariableTimeAxis']):
    __slots__ = ['__data']
    __LIKE_NP_FUNCTIONS__ = {'zeros_like', 'empty_like', 'ones_like'}

    def __init__(self, values: np.array = None, meta: Dict = None, name: str = "time", data: DataContainer = None):
        if data is not None:
            self.__data = data
        else:
            if values.dtype != np.dtype('datetime64[ns]'):
                raise ValueError(
                    f"Please provide datetime64[ns] for time axis, got {values.dtype}")
            self.__data = DataContainer(
                values=values, name=name, meta=meta, is_time_dependent=True)

    def to_dictionary(self, array_to_list=False) -> Dict[str, object]:
        d = self.__data.to_dictionary(array_to_list=array_to_list)
        d.update({"type": "VariableTimeAxis"})
        return d

    def select(self, indices, inplace=False) -> "VariableTimeAxis":
        if inplace:
            res = self
        else:
            res = deepcopy(self)
        res.__data.select(indices, inplace=True)
        return res

    def zeros_like(self) -> "VariableTimeAxis":
        return VariableTimeAxis(data=DataContainer.zeros_like(self.__data))

    def ones_like(self) -> "VariableTimeAxis":
        return VariableTimeAxis(data=DataContainer.ones_like(self.__data))

    def empty_like(self) -> "VariableTimeAxis":
        return VariableTimeAxis(data=DataContainer.empty_like(self.__data))

    @property
    def shape(self):
        return self.__data.shape

    def astype(self, dtype) -> 'VariableTimeAxis':
        return VariableTimeAxis(data=self.__data.astype(dtype))

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Union[str, Dict[str, str], List]], time=None) -> "VariableTimeAxis":
        assert dictionary['type'] == "VariableTimeAxis"
        return VariableTimeAxis(data=DataContainer.from_dictionary(dictionary, dtype=np.dtype('datetime64[ns]')))

    @staticmethod
    def reserve_like(other: 'VariableTimeAxis', length: int = 0) -> 'VariableTimeAxis':
        return VariableTimeAxis(data=DataContainer.reserve_like(other.__data, length))

    def __getitem__(self, key):
        return self.view(key)

    def __setitem__(self, k, v: Union['VariableTimeAxis', float, int]):
        if type(v) is VariableTimeAxis:
            self.__data[k] = v.__data
        else:
            self.__data[k] = v

    def __len__(self):
        return len(self.__data)

    def __array_function__(self, func, types, args, kwargs):
        if func.__name__ in VariableTimeAxis.__LIKE_NP_FUNCTIONS__:
            return VariableTimeAxis.__dict__[func.__name__].__func__(self)
        if 'out' in kwargs:
            raise ValueError("out parameter is not supported")
        f_args = [_data_container(arg) for arg in args]
        f_kwargs = {name: _data_container(value) for name, value in kwargs.items()}
        res = func(*f_args, **f_kwargs)

        if isinstance(res, DataContainer):
            return VariableTimeAxis(data=res)
        return res

    def __array_ufunc__(self, ufunc, method, *inputs, out: 'VariableTimeAxis' or None = None, **kwargs):
        if out is not None:
            _out = _data_container(out[0])
        else:
            _out = None

        res = self.__data.__array_ufunc__(ufunc, method, *inputs, out=_out, **kwargs)

        if _out is not None:
            return out[0]
        if isinstance(res, DataContainer):
            return VariableTimeAxis(data=res)
        return res

    def view(self, index_range: Union[slice, np.ndarray]) -> 'VariableTimeAxis':
        return VariableTimeAxis(data=self.__data[index_range])

    def __eq__(self, other: 'VariableTimeAxis') -> bool:
        return type(other) is VariableTimeAxis and self.__data == other.__data

    @property
    def is_time_dependent(self) -> bool:
        return True

    @property
    def values(self) -> np.array:
        return self.__data.values

    @property
    def data_container(self) -> DataContainer:
        return self.__data

    @property
    def unit(self) -> str:
        return 'ns'

    @property
    def name(self) -> str:
        return self.__data.name

    @property
    def nbytes(self) -> int:
        return self.__data.nbytes

    @property
    def meta(self) -> Dict:
        return self.__data.meta

    @property
    def dtype(self) -> np.dtype:
        return self.__data.dtype
