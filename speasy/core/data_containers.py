from datetime import datetime
from sys import getsizeof
from typing import Dict, List

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
        return np.searchsorted(time, np.datetime64(key, 'ns'), side='left')
    if isinstance(key, np.datetime64):
        return np.searchsorted(time, key, side='left')


class DataContainer(object):
    __slots__ = ['__values', '__name', '__meta', '__is_time_dependent']

    def __init__(self, values: np.array, meta: Dict = None, name: str = None, is_time_dependent: bool = True):
        self.__values = values
        self.__is_time_dependent = is_time_dependent
        self.__name = name or ""
        self.__meta = meta or {}

    def reshape(self, new_shape):
        self.__values = self.__values.reshape(new_shape)

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
    def unit(self) -> str:
        return self.__meta.get('UNITS')

    @property
    def nbytes(self) -> int:
        return self.__values.nbytes + getsizeof(self.__meta) + getsizeof(self.__name)

    def view(self, index_range: slice):
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
            "is_time_dependent": self.is_time_dependent
        }

    @staticmethod
    def from_dictionary(dictionary: Dict[str, str or Dict[str, str] or List], dtype=np.float64) -> "DataContainer":
        try:
            return DataContainer(values=np.array(dictionary["values"], dtype=dtype), meta=dictionary["meta"],
                                 name=dictionary["name"],
                                 is_time_dependent=dictionary["is_time_dependent"])
        except ValueError:
            return DataContainer(values=np.array(dictionary["values"]), meta=dictionary["meta"],
                                 name=dictionary["name"],
                                 is_time_dependent=dictionary["is_time_dependent"])

    @staticmethod
    def reserve_like(other: 'DataContainer', length: int = 0) -> 'DataContainer':
        return DataContainer(name=other.__name, meta=other.__meta,
                             values=np.empty(
                                 (length,) + other.shape[1:], dtype=other.__values.dtype),
                             is_time_dependent=other.__is_time_dependent
                             )

    def __len__(self):
        return len(self.__values)

    def __getitem__(self, key):
        return self.view(key)

    def __setitem__(self, k, v: 'DataContainer'):
        assert type(v) is DataContainer
        self.__values[k] = v.__values

    def __eq__(self, other: 'DataContainer') -> bool:
        return self.__meta == other.__meta and \
               self.__name == other.__name and \
               self.is_time_dependent == other.is_time_dependent and \
               np.all(self.__values.shape == other.__values.shape) and \
               np.array_equal(self.__values, other.__values, equal_nan=True)

    def replace_val_by_nan(self, val):
        if self.__values.dtype != np.float64:
            self.__values = self.__values.astype(np.float64)
        self.__values[self.__values == val] = np.nan

    @property
    def meta(self):
        return self.__meta

    @property
    def name(self):
        return self.__name


class VariableAxis(object):
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

    @staticmethod
    def from_dictionary(dictionary: Dict[str, str or Dict[str, str] or List], time=None) -> "VariableAxis":
        assert dictionary['type'] == "VariableAxis"
        return VariableAxis(data=DataContainer.from_dictionary(dictionary))

    @staticmethod
    def reserve_like(other: 'VariableAxis', length: int = 0) -> 'VariableAxis':
        return VariableAxis(data=DataContainer.reserve_like(other.__data, length))

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(slice(_to_index(key.start, self.__data.values), _to_index(key.stop, self.__data.values)))

    def __setitem__(self, k, v: 'VariableAxis'):
        assert type(v) is VariableAxis
        self.__data[k] = v.__data

    def __len__(self):
        return len(self.__data)

    def view(self, index_range: slice) -> 'VariableAxis':
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


class VariableTimeAxis(object):
    __slots__ = ['__data']

    def __init__(self, values: np.array = None, meta: Dict = None, data: DataContainer = None):
        if data is not None:
            self.__data = data
        else:
            if values.dtype != np.dtype('datetime64[ns]'):
                raise ValueError(
                    f"Please provide datetime64[ns] for time axis, got {values.dtype}")
            self.__data = DataContainer(
                values=values, name='time', meta=meta, is_time_dependent=True)

    def to_dictionary(self, array_to_list=False) -> Dict[str, object]:
        d = self.__data.to_dictionary(array_to_list=array_to_list)
        d.update({"type": "VariableTimeAxis"})
        return d

    @property
    def shape(self):
        return self.__data.shape

    @staticmethod
    def from_dictionary(dictionary: Dict[str, str or Dict[str, str] or List], time=None) -> "VariableTimeAxis":
        assert dictionary['type'] == "VariableTimeAxis"
        return VariableTimeAxis(data=DataContainer.from_dictionary(dictionary, dtype=np.dtype('datetime64[ns]')))

    @staticmethod
    def reserve_like(other: 'VariableTimeAxis', length: int = 0) -> 'VariableTimeAxis':
        return VariableTimeAxis(data=DataContainer.reserve_like(other.__data, length))

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(key)

    def __setitem__(self, k, v: 'VariableTimeAxis'):
        assert type(v) is VariableTimeAxis
        self.__data[k] = v.__data

    def __len__(self):
        return len(self.__data)

    def view(self, index_range: slice) -> "VariableTimeAxis":
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
