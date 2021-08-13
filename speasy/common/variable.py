import numpy as np
import pandas as pds
from datetime import datetime
from typing import List, Optional
from . import deprecation


class SpeasyVariable(object):
    """SpeasyVariable object. Base class for storing variable data.

    :param time: time data
    :type time: numpy.ndarray
    :param data: data
    :type data: numpy.ndarray
    :param meta: metadata
    :type meta: dict
    :param columns: column names
    :type columns: list[str]
    :param y:
    :type y:

    """
    __slots__ = ['meta', 'time', 'values', 'columns', 'y']

    def __init__(self, time=np.empty(0), data=np.empty((0, 1)), meta: Optional[dict] = None,
                 columns: Optional[list[str]] = None, y: Optional[np.ndarray] = None):
        """Constructor
        """
        self.meta = meta or {}
        self.columns = columns or []
        if len(data.shape) == 1:
            self.values = data.reshape((data.shape[0], 1))  # to be consistent with pandas
        else:
            self.values = data
        self.time = time
        self.y = y

    def view(self, time_range):
        """Return view of the current variable within the desired :data:`time_range`.

        :param time_range: time range
        :type time_range: speasy.common.datetime_range.DateTimeRange
        :return: view of the variable
        :rtype: speasy.common.variable.SpeasyVariable
        """
        return SpeasyVariable(self.time[time_range], self.values[time_range], self.meta, self.columns, self.y)

    def __eq__(self, other: 'SpeasyVariable') -> bool:
        """Check if this variable equals another.

        :param other: another SpeasyVariable object
        :type other: speasy.common.variable.SpeasyVariable
        :return: condition result
        :rtype: bool
        """
        return self.meta == other.meta and \
               self.columns == other.columns and \
               len(self.time) == len(other.time) and \
               np.all(self.time == other.time) and \
               np.all(self.values == other.values)

    def __len__(self):
        """Get lenght of the timeseries
        """
        return len(self.time)

    def __getitem__(self, key):
        """Item getter

        :param key: key
        :type key: slice
        :return: data slice
        :rtype: speasy.common.variable.SpeasyVariable
        """
        if isinstance(key, slice):
            if isinstance(key.start, int) or isinstance(key.stop, int) or (key.start is None and key.stop is None):
                return self.view(key)
            if isinstance(key.start, float) or isinstance(key.stop, float):
                start = self.time[0] - 1. if key.start is None else key.start
                stop = self.time[-1] + 1. if key.stop is None else key.stop
                return self.view(np.logical_and(self.time >= start, self.time < stop))
            if isinstance(key.start, datetime):
                start = self.time[0] - 1. if key.start is None else key.start.timestamp()
                stop = self.time[-1] + 1. if key.stop is None else key.stop.timestamp()
                return self.view(np.logical_and(self.time >= start, self.time < stop))

    def to_dataframe(self, datetime_index=False) -> pds.DataFrame:
        """Convert the variable to a pandas.DataFrame object.

        :param datetime_index: boolean indicating that the index is datetime
        :type datetime_index: bool
        :return: dataframe
        :rtype: pandas.DataFrame
        """
        if datetime_index:
            time = pds.to_datetime(self.time, unit='s')
        else:
            time = self.time
        return pds.DataFrame(index=time, data=self.values, columns=self.columns, copy=True)

    def plot(self, *args, **kwargs):
        """Plot the variable.

        :param args: args
        :type args: tuple
        :param kwargs: kwargs
        :type kwargs: dict
        :return: plot
        """
        return self.to_dataframe(datetime_index=True).plot(*args, **kwargs)

    @property
    def data(self):
        deprecation('data will be removed soon')
        return self.values

    @data.setter
    def data(self, values):
        deprecation('data will be removed soon')
        self.values = values

    @staticmethod
    def from_dataframe(df: pds.DataFrame) -> 'SpeasyVariable':
        """Load from pandas.DataFrame object.

        :param df: dataframe
        :type df: pandas.DataFrame
        :return: speasy variable object
        :rtype: speasy.common.variable.SpeasyVariable
        """
        if hasattr(df.index[0], 'timestamp'):
            time = np.array([d.timestamp() for d in df.index])
        else:
            time = df.index.values
        return SpeasyVariable(time=time, data=df.values, meta={}, columns=list(df.columns))


def from_dataframe(df: pds.DataFrame) -> SpeasyVariable:
    """Convert a dataframe to SpeasyVariable.

    :param df: input dataframe
    :type df: pandas.DataFrame
    :return: speasy variable
    :rtype: speasy.common.variable.SpeasyVariable
    """
    return SpeasyVariable.from_dataframe(df)


def to_dataframe(var: SpeasyVariable, datetime_index=False) -> pds.DataFrame:
    """Convert a :class:`~speasy.common.variable.SpeasyVariable` to pandas.DataFrame.

    :param var: variable to convert
    :type var: speasy.common.variable.SpeasyVariable
    :param datetime_index: index is datetime
    :type datetime_index: bool
    :return: pandas dataframe
    :rtype: pandas.DataFrame
    """
    return SpeasyVariable.to_dataframe(var, datetime_index)


def merge(variables: List[SpeasyVariable]) -> Optional[SpeasyVariable]:
    """Merge a list of :class:`~speasy.common.variable.SpeasyVariable` objects.

    :param variables: list of variables
    :type variable: list[speasy.common.variable.SpeasyVariable]
    """
    if len(variables) == 0:
        return None
    variables = [v for v in variables if v is not None]
    sorted_var_list = [v for v in variables if len(v.time)]
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
        return SpeasyVariable(columns=variables[0].columns, meta=variables[0].meta, y=variables[0].y)

    overlaps = [np.where(current.time >= nxt.time[0])[0][0] if current.time[-1] >= nxt.time[0] else -1 for current, nxt
                in
                zip(sorted_var_list[:-1], sorted_var_list[1:])]

    dest_len = int(np.sum(
        [overlap if overlap != -1 else len(r.time) for overlap, r in zip(overlaps, sorted_var_list[:-1])]))
    dest_len += len(sorted_var_list[-1].time)

    time = np.zeros(dest_len)
    data = np.zeros((dest_len, sorted_var_list[0].values.shape[1])) if len(
        sorted_var_list[0].values.shape) == 2 else np.zeros(dest_len)

    units = set([var.values.unit for var in sorted_var_list if hasattr(var.values, 'unit')])
    if len(units) == 1:
        data *= units[0]

    pos = 0
    for r, overlap in zip(sorted_var_list, overlaps + [-1]):
        frag_len = len(r.time) if overlap == -1 else overlap
        time[pos:pos + frag_len] = r.time[0:frag_len]
        data[pos:pos + frag_len] = r.values[0:frag_len]
        pos += frag_len
    return SpeasyVariable(time, data, sorted_var_list[0].meta, sorted_var_list[0].columns, y=sorted_var_list[0].y)
