from copy import deepcopy, copy
from datetime import datetime, timezone
from sys import getsizeof
from typing import Dict, List, Protocol, TypeVar, Union, Any

import astropy.units
import numpy as np


def _name(input_p: Any) -> str:
    if hasattr(input_p, "name"):
        return input_p.name
    return str(input)


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
    if type(key) in (int, np.int64, np.int32, np.uint64, np.uint32):
        return key
    if isinstance(key, float):
        return np.searchsorted(time, np.datetime64(int(key * 1e9), 'ns'), side='left')
    if isinstance(key, datetime):
        without_tz = key.astimezone(timezone.utc).replace(tzinfo=None)
        return np.searchsorted(time, np.datetime64(without_tz, 'ns'), side='left')
    if isinstance(key, np.datetime64):
        return np.searchsorted(time, key, side='left')


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
        except (ValueError, KeyError):
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
                values=np.array(dictionary["values"], dtype=dictionary.get("values_type", dtype)),
                meta=dictionary["meta"],
                name=dictionary["name"],
                is_time_dependent=dictionary["is_time_dependent"]
            )
        except ValueError:
            return DataContainer(
                values=np.array(dictionary["values"]), meta=dictionary["meta"],
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


class VariableAxis(DataContainerProtocol['VariableAxis']):
    __slots__ = ['__data']
    __LIKE_NP_FUNCTIONS__ = {'zeros_like', 'empty_like', 'ones_like'}

    def __init__(self, values: np.array = None, meta: Dict = None, name: str = "", is_time_dependent: bool = False,
                 data: DataContainer = None):
        if data is not None:
            self.__data = data
        else:
            self.__data = DataContainer(
                values=values, name=name, meta=meta, is_time_dependent=is_time_dependent)

    def zeros_like(self) -> "VariableAxis":
        return VariableAxis(data=DataContainer.zeros_like(self.__data))

    def ones_like(self) -> "VariableAxis":
        return VariableAxis(data=DataContainer.ones_like(self.__data))

    def empty_like(self) -> "VariableAxis":
        return VariableAxis(data=DataContainer.empty_like(self.__data))


    def to_dictionary(self, array_to_list=False) -> Dict[str, object]:
        d = self.__data.to_dictionary(array_to_list=array_to_list)
        d.update({"type": "VariableAxis"})
        return d

    def select(self, indices, inplace=False) -> "VariableAxis":
        if inplace:
            res = self
        else:
            res = deepcopy(self)
        res.__data.select(indices, inplace=True)
        return res

    @staticmethod
    def from_dictionary(dictionary: Dict[str, Union[str, Dict[str, str], List]], time=None) -> "VariableAxis":
        assert dictionary['type'] == "VariableAxis"
        return VariableAxis(data=DataContainer.from_dictionary(dictionary))

    @staticmethod
    def reserve_like(other: 'VariableAxis', length: int = 0) -> 'VariableAxis':
        return VariableAxis(data=DataContainer.reserve_like(other.__data, length))

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(slice(_to_index(key.start, self.__data.values), _to_index(key.stop, self.__data.values)))
        else:
            return self.view(key)

    def __setitem__(self, k, v: Union['VariableAxis', float, int]):
        if type(v) is VariableAxis:
            self.__data[k] = v.__data
        else:
            self.__data[k] = v

    def __len__(self):
        return len(self.__data)

    def view(self, index_range: Union[slice, np.ndarray]) -> 'VariableAxis':
        return VariableAxis(data=self.__data[index_range])

    def __eq__(self, other: 'VariableAxis') -> bool:
        return type(other) is VariableAxis and self.__data == other.__data

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
        return VariableAxis(data=self.__data.astype(dtype))

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
