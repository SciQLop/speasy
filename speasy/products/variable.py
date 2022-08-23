import numpy as np
import pandas as pds
from datetime import datetime
from typing import List, Optional
from speasy.core import deprecation
from copy import deepcopy

import astropy.units
import astropy.table


def _to_index(key, time):
    if key is None:
        return None
    if type(key) is int:
        return key
    if isinstance(key, float):
        return np.searchsorted(time, np.datetime64(int(key * 1e9), 'ns'), side='left')
    if isinstance(key, datetime):
        return np.searchsorted(time, np.datetime64(key, 'ns'), side='left')


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
    __slots__ = ['__meta', '__time', '__values', '__columns', '__axes']

    def __init__(self, time=np.empty(0, dtype=np.dtype('datetime64[ns]')), values=np.empty((0, 1)),
                 meta: Optional[dict] = None,
                 columns: Optional[List[str]] = None, extra_axes: Optional[List[np.ndarray]] = None):
        """Constructor
        """

        if time.dtype != np.dtype('datetime64[ns]'):
            raise ValueError(f"Please provide datetime64[ns] for time axis, got {time.dtype}")
        if len(time) != len(values):
            raise ValueError(f"Time and data must have the same length, got time:{len(time)} and data:{len(values)}")

        self.__meta = meta or {}
        self.__columns = columns or []
        if len(values.shape) == 1:
            self.__values = values.reshape((values.shape[0], 1))  # to be consistent with pandas
        else:
            self.__values = values
        self.__time = time
        self.__axes = [time] + (extra_axes or [])

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
        extra_axes = []
        for axis in self.__axes[1:]:
            if axis is not None:
                if len(axis.shape) > 1 and axis.shape[0] == len(self.__time):
                    extra_axes.append(axis[index_range])
                else:
                    extra_axes.append(axis)
            else:
                extra_axes.append(None)  # maybe this should be avoided
        return SpeasyVariable(time=self.__time[index_range], values=self.__values[index_range], meta=self.__meta,
                              columns=self.__columns, extra_axes=extra_axes)

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
        return self.__meta == other.__meta and \
               self.__columns == other.__columns and \
               len(self.time) == len(other.time) and \
               np.all([ np.all(lhs == rhs) for lhs, rhs in zip(self.axes, other.axes)]) and \
               np.all(self.__values == other.values)

    def __len__(self):
        return len(self.time)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(slice(_to_index(key.start, self.time), _to_index(key.stop, self.time)))

    def to_dataframe(self) -> pds.DataFrame:
        """Convert the variable to a pandas.DataFrame object.

        Parameters
        ----------
        Returns
        -------
        pandas.DataFrame:
            Variable converted to Pandas DataFrame
        """
        return pds.DataFrame(index=self.time, data=self.values, columns=self.__columns, copy=True)

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
            units = astropy.units.Unit(self.meta["PARAMETER_UNITS"])
        except (ValueError, KeyError):
            units = None
        df = self.to_dataframe()
        umap = {c: units for c in df.columns}
        return astropy.table.Table.from_pandas(df, units=umap, index=True)

    def plot(self, *args, **kwargs):
        """Plot the variable.

        See https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.html

        """
        return self.to_dataframe().plot(*args, **kwargs)

    @property
    def data(self):
        deprecation('data will be removed soon')
        return self.__values

    @property
    def values(self):
        return self.__values

    @property
    def time(self):
        return self.__time

    @property
    def meta(self):
        return self.__meta

    @property
    def axes(self):
        return self.__axes

    @property
    def columns(self):
        return self.__columns

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
        return SpeasyVariable(time=time, values=df.values, meta={}, columns=list(df.columns))

    @staticmethod
    def epoch_to_datetime64(epoch_array: np.array):
        return (epoch_array * 1e9).astype('datetime64[ns]')

    def replace_fillval_by_nan(self, inplace=False) -> 'SpeasyVariable':
        if inplace:
            res = self
        else:
            res = deepcopy(self)
        if 'FILLVAL' in res.meta:
            res.values[res.values == res.meta['FILLVAL']] = np.nan
        return res


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
        return SpeasyVariable(columns=variables[0].columns, meta=variables[0].meta,
                              extra_axes=variables[0].axes[1:])

    overlaps = [np.where(current.time >= nxt.time[0])[0][0] if current.time[-1] >= nxt.time[0] else -1 for current, nxt
                in
                zip(sorted_var_list[:-1], sorted_var_list[1:])]

    dest_len = int(np.sum(
        [overlap if overlap != -1 else len(r.time) for overlap, r in zip(overlaps, sorted_var_list[:-1])]))
    dest_len += len(sorted_var_list[-1].time)

    time = np.zeros(dest_len, dtype=np.dtype('datetime64[ns]'))
    values = np.zeros((dest_len,) + sorted_var_list[0].values.shape[1:])

    extra_axes = []
    for axis in sorted_var_list[0].axes[1:]:
        if axis is not None:
            if len(axis.shape) > 1 and axis.shape[0] == len(sorted_var_list[0].time):
                extra_axes.append(np.zeros((dest_len, *axis.shape[1:]), dtype=axis.dtype))
            else:
                extra_axes.append(axis.copy())
        else:
            extra_axes.append(None)

    units = set([var.values.unit for var in sorted_var_list if hasattr(var.values, 'unit')])
    if len(units) == 1:
        values <<= units.pop()
    elif len(units) > 1:
        raise ValueError("Merging variables with different units")

    pos = 0
    for r, overlap in zip(sorted_var_list, overlaps + [-1]):
        frag_len = len(r.time) if overlap == -1 else overlap
        time[pos:(pos + frag_len)] = r.time[0:frag_len]
        values[pos:(pos + frag_len)] = r.values[0:frag_len]
        for axis, src_axis in zip(extra_axes, r.axes[1:]):
            if axis is not None:
                if len(axis.shape) > 1 and axis.shape[0] == dest_len:
                    axis[pos:(pos + frag_len)] = src_axis[0:frag_len]
        pos += frag_len
    return SpeasyVariable(time=time, values=values, meta=sorted_var_list[0].meta, columns=sorted_var_list[0].columns,
                          extra_axes=extra_axes)
