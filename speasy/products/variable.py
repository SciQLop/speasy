import numpy as np
import pandas as pds
from datetime import datetime
from typing import List, Optional, Dict
from speasy.plotting import Plot
from copy import deepcopy

import astropy.units
import astropy.table


def _to_index(key, time):
    if key is None:
        return None
    if type(key) in (int, np.int64, np.int32, np.uint64, np.uint32):
        return key
    if isinstance(key, float):
        return np.searchsorted(time, np.datetime64(int(key * 1e9), 'ns'), side='left')
    if isinstance(key, datetime):
        return np.searchsorted(time, np.datetime64(key, 'ns'), side='left')


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
    def is_time_dependent(self):
        return self.__is_time_dependent

    @property
    def values(self):
        return self.__values

    @property
    def shape(self):
        return self.__values.shape

    def view(self, index_range: slice):
        return DataContainer(name=self.__name, meta=self.__meta, values=self.__values[index_range],
                             is_time_dependent=self.__is_time_dependent)

    def to_dictionary(self) -> Dict[str, object]:
        return {
            "values": self.__values.copy(),
            "meta": self.__meta.copy(),
            "name": self.__name,
            "is_time_dependent": self.is_time_dependent
        }

    @staticmethod
    def from_dictionary(dictionary: Dict[str, str or Dict[str, str] or List], dtype=np.float) -> "DataContainer":
        return DataContainer(values=np.array(dictionary["values"], dtype=dtype), meta=dictionary["meta"],
                             name=dictionary["name"],
                             is_time_dependent=dictionary["is_time_dependent"])

    @staticmethod
    def reserve_like(other: 'DataContainer', length: int = 0) -> 'DataContainer':
        return DataContainer(name=other.__name, meta=other.__meta,
                             values=np.empty((length,) + other.shape[1:], dtype=other.__values.dtype),
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
               np.all(self.__values == other.__values)

    def replace_val_by_nan(self, val):
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
            self.__data = DataContainer(values=values, name=name, meta=meta, is_time_dependent=is_time_dependent)

    def to_dictionary(self) -> Dict[str, object]:
        d = self.__data.to_dictionary()
        d.update({"type": "VariableAxis"})
        return d

    @staticmethod
    def from_dictionary(dictionary: Dict[str, str or Dict[str, str] or List], time=None) -> "VariableAxis":
        assert dictionary['type'] == "VariableAxis"
        return VariableAxis(DataContainer.from_dictionary(dictionary))

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
    def is_time_dependent(self):
        return self.__data.is_time_dependent

    @property
    def values(self):
        return self.__data.values

    @property
    def shape(self):
        return self.__data.shape


class VariableTimeAxis(object):
    __slots__ = ['__data']

    def __init__(self, values: np.array = None, meta: Dict = None, data: DataContainer = None):
        if data is not None:
            self.__data = data
        else:
            if values.dtype != np.dtype('datetime64[ns]'):
                raise ValueError(f"Please provide datetime64[ns] for time axis, got {values.dtype}")
            self.__data = DataContainer(values=values, name='time', meta=meta, is_time_dependent=True)

    def to_dictionary(self) -> Dict[str, object]:
        d = self.__data.to_dictionary()
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

    def view(self, index_range: slice):
        return VariableTimeAxis(data=self.__data[index_range])

    def __eq__(self, other: 'VariableTimeAxis') -> bool:
        return type(other) is VariableTimeAxis and self.__data == other.__data

    @property
    def is_time_dependent(self):
        return True

    @property
    def values(self):
        return self.__data.values


class SpeasyVariable(object):
    """SpeasyVariable object. Base class for storing variable data.

    Attributes
    ----------
    time: numpy.ndarray
        time vector (x-axis data)
    values: numpy.ndarray
        data
    meta: Optional[dict]
        metadata
    columns: Optional[List[str]]
        column names
    axes: Optional[List[np.ndarray]]
        Collection composed of time axis plus eventual additional axes according to values' shape

    Methods
    -------
    view:
        Return view of the current variable within the desired :data:`time_range`
    to_dataframe:
        Convert the variable to a pandas.DataFrame object
    plot:
        Plot the data with matplotlib

    """
    __slots__ = ['__values_container', '__columns', '__axes']

    def __init__(self, axes: List[VariableAxis or VariableTimeAxis], values: DataContainer,
                 columns: Optional[List[str]] = None):
        if not isinstance(axes[0], VariableTimeAxis):
            raise TypeError(f"axes[0] must be a VariableTimeAxis instance, got {type(axes[0])}")
        if axes[0].shape[0] != values.shape[0]:
            raise ValueError(
                f"Time and data must have the same length, got time:{len(axes[0])} and data:{len(values)}")

        self.__columns = columns or []
        if len(values.values.shape) == 1:
            values.reshape((values.shape[0], 1))  # to be consistent with pandas

        self.__values_container = values
        self.__axes = axes

    def view(self, index_range: slice):
        """Return view of the current variable within the desired :data:`time_range`.

        Parameters
        ----------
        index_range: slice
            index range

        Returns
        -------
        speasy.common.variable.SpeasyVariable
            view of the variable on the given range
        """
        return SpeasyVariable(axes=[axis[index_range] if axis.is_time_dependent else axis for axis in self.__axes],
                              values=self.__values_container[index_range])

    def __eq__(self, other: 'SpeasyVariable') -> bool:
        """Check if this variable equals another.

        Parameters
        ----------
        other: speasy.common.variable.SpeasyVariable
            another SpeasyVariable object to compare with

        Returns
        -------
        bool:
            True if all attributes are equal
        """
        return type(
            other) is SpeasyVariable and self.__axes == other.__axes and self.__values_container == other.__values_container

    def __len__(self):
        return len(self.__axes[0])

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(slice(_to_index(key.start, self.time), _to_index(key.stop, self.time)))

    def __setitem__(self, k, v: 'SpeasyVariable'):
        assert type(v) is SpeasyVariable
        self.__values_container[k] = v.__values_container
        for axis, src_axis in zip(self.__axes, v.__axes):
            if axis.is_time_dependent:
                axis[k] = src_axis

    @property
    def name(self):
        return self.__values_container.name

    @property
    def values(self):
        return self.__values_container.values

    @property
    def time(self):
        return self.__axes[0].values

    @property
    def meta(self):
        return self.__values_container.meta

    @property
    def axes(self):
        return self.__axes

    @property
    def axes_labels(self):
        return [axis.name for axis in self.__axes]

    @property
    def columns(self):
        return self.__columns

    def to_astropy_table(self) -> astropy.table.Table:
        """Convert the variable to a astropy.Table object.

        Parameters
        ----------
        datetime_index: bool
            boolean indicating that the index is datetime

        Returns
        -------
        astropy.Table:
            Variable converted to astropy.Table
        """
        try:
            units = astropy.units.Unit(self.meta["UNITS"])
        except (ValueError, KeyError):
            units = None
        df = self.to_dataframe()
        umap = {c: units for c in df.columns}
        return astropy.table.Table.from_pandas(df, units=umap, index=True)

    def to_dataframe(self) -> pds.DataFrame:
        """Convert the variable to a pandas.DataFrame object.

        Parameters
        ----------
        Returns
        -------
        pandas.DataFrame:
            Variable converted to Pandas DataFrame
        """
        if len(self.__values_container.shape) != 2:
            raise ValueError(
                f"Cant' convert a SpeasyVariable with shape {self.__values_container.shape} to DataFrame, only 1D/2D variables are accepted")
        return pds.DataFrame(index=self.time, data=self.values, columns=self.__columns, copy=True)

    @staticmethod
    def from_dataframe(df: pds.DataFrame) -> 'SpeasyVariable':
        """Load from pandas.DataFrame object.

        Parameters
        ----------
        dr: pandas.DataFrame
            Input DataFrame to convert

        Returns
        -------
        SpeasyVariable:
            Variable created from DataFrame
        """
        if df.index.dtype == np.dtype('datetime64[ns]'):
            time = np.array(df.index)
        elif hasattr(df.index[0], 'timestamp'):
            time = np.array([np.datetime64(d.timestamp() * 1e9, 'ns') for d in df.index])
        else:
            raise ValueError("Can't convert DataFrame index to datetime64[ns] array")
        return SpeasyVariable(axes=[VariableTimeAxis(values=time, meta={})],
                              values=DataContainer(values=df.values, meta={}, name='Unknown'),
                              columns=list(df.columns))

    def to_dictionary(self) -> Dict[str, object]:
        return {
            'axes': [axis.to_dictionary() for axis in self.__axes],
            'values': self.__values_container.to_dictionary(),
            'columns': deepcopy(self.__columns)
        }

    @staticmethod
    def from_dictionary(dictionary: Dict[str, object] or None) -> 'SpeasyVariable' or None:
        if dictionary is not None:
            axes = dictionary['axes']
            axes = [VariableTimeAxis.from_dictionary(axes[0])] + [VariableAxis.from_dictionary(axis) for axis in
                                                                  axes[1:]]

            return SpeasyVariable(
                values=DataContainer.from_dictionary(dictionary['values']),
                axes=axes,
                columns=dictionary.get('columns', None)
            )
        else:
            return None

    @staticmethod
    def epoch_to_datetime64(epoch_array: np.array):
        return (epoch_array * 1e9).astype('datetime64[ns]')

    @property
    def plot(self, *args, **kwargs):
        """Plot the variable.

        See https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.html

        """
        return Plot(values=self.values, columns_names=self.columns, axes=self.axes, metadata=self.meta)

    def replace_fillval_by_nan(self, inplace=False) -> 'SpeasyVariable':
        if inplace:
            res = self
        else:
            res = deepcopy(self)
        if 'FILLVAL' in res.meta:
            res.__values_container.replace_val_by_nan(res.meta['FILLVAL'])
        return res

    @staticmethod
    def reserve_like(other: 'SpeasyVariable', length: int = 0) -> 'SpeasyVariable':
        axes = []
        for axis in other.__axes:
            if axis.is_time_dependent:
                new_axis = type(axis).reserve_like(axis, length)
                axes.append(new_axis)
            else:
                axes.append(deepcopy(axis))
        return SpeasyVariable(values=DataContainer.reserve_like(other.__values_container, length), axes=axes,
                              columns=other.columns)


def to_dictionary(var: SpeasyVariable) -> Dict[str, object]:
    return var.to_dictionary()


def from_dictionary(dictionary: Dict[str, object] or None) -> SpeasyVariable or None:
    return SpeasyVariable.from_dictionary(dictionary)


def from_dataframe(df: pds.DataFrame) -> SpeasyVariable:
    """Convert a dataframe to SpeasyVariable.

    See Also
    --------
    SpeasyVariable.from_dataframe
    """
    return SpeasyVariable.from_dataframe(df)


def to_dataframe(var: SpeasyVariable) -> pds.DataFrame:
    """Convert a :class:`~speasy.common.variable.SpeasyVariable` to pandas.DataFrame.

    See Also
    --------
    SpeasyVariable.to_dataframe
    """
    return SpeasyVariable.to_dataframe(var)


def merge(variables: List[SpeasyVariable]) -> Optional[SpeasyVariable]:
    """Merge a list of :class:`~speasy.common.variable.SpeasyVariable` objects.

    Parameters
    ----------
    variables: List[SpeasyVariable]
        Variables to merge together

    Returns
    -------
    SpeasyVariable:
        Resulting variable from merge operation
    """
    if len(variables) == 0:
        return None
    sorted_var_list = [v for v in variables if (v is not None) and (len(v.time) > 0)]
    sorted_var_list.sort(key=lambda v: v.time[0])

    # drop variables covered by previous ones
    for prev, current in zip(sorted_var_list[:-1], sorted_var_list[1:]):
        if prev.time[-1] >= current.time[-1]:
            sorted_var_list.remove(current)

    # drop variables covered by next ones
    for current, nxt in zip(sorted_var_list[:-1], sorted_var_list[1:]):
        if nxt.time[0] == current.time[0] and nxt.time[-1] >= current.time[-1]:
            sorted_var_list.remove(current)

    if len(sorted_var_list) == 0:
        return SpeasyVariable.reserve_like(variables[0], length=0)

    overlaps = [np.where(current.time >= nxt.time[0])[0][0] if current.time[-1] >= nxt.time[0] else -1 for current, nxt
                in
                zip(sorted_var_list[:-1], sorted_var_list[1:])]

    dest_len = int(np.sum(
        [overlap if overlap != -1 else len(r.time) for overlap, r in zip(overlaps, sorted_var_list[:-1])]))
    dest_len += len(sorted_var_list[-1].time)

    result = SpeasyVariable.reserve_like(sorted_var_list[0], dest_len)

    units = set([var.values.unit for var in sorted_var_list if hasattr(var.values, 'unit')])
    if len(units) == 1:
        result.values <<= units.pop()
    elif len(units) > 1:
        raise ValueError("Merging variables with different units")
    pos = 0

    for r, overlap in zip(sorted_var_list, overlaps + [-1]):
        frag_len = len(r.time) if overlap == -1 else overlap
        result[pos:(pos + frag_len)] = r[0:frag_len]
        # time[pos:(pos + frag_len)] = r.time[0:frag_len]
        # values[pos:(pos + frag_len)] = r.values[0:frag_len]

        pos += frag_len
    return result
