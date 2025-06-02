from copy import deepcopy
from datetime import datetime, timezone
from sys import getsizeof
from typing import Dict, List, Protocol, TypeVar, Union

import astropy.units
import numpy as np


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

    def view(self, index_range: Union[slice, np.ndarray]) -> T:
        ...


class DataContainer(DataContainerProtocol['DataContainer']):
    __slots__ = ['__values', '__name', '__meta', '__is_time_dependent']

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
        return DataContainer(values=self.__values.astype(dtype), meta=self.__meta, name=self.__name,
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

    @property
    def meta(self):
        return self.__meta

    @property
    def name(self):
        return self.__name


class VariableAxis(DataContainerProtocol['VariableAxis']):
    __slots__ = ['__data']

    def __init__(self, values: np.array = None, meta: Dict = None, name: str = "", is_time_dependent: bool = False,
                 data: DataContainer = None):
        if data is not None:
            self.__data = data
        else:
            self.__data = DataContainer(
                values=values, name=name, meta=meta, is_time_dependent=is_time_dependent)

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


class VariableTimeAxis(DataContainerProtocol['VariableTimeAxis']):
    __slots__ = ['__data']

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

    @property
    def shape(self):
        return self.__data.shape

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
