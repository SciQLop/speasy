import numpy as np
import pandas as pds
from datetime import datetime
from typing import List, Optional
from . import deprecation


class SpwcVariable(object):
    __slots__ = ['meta', 'time', 'values', 'columns', 'y']

    def __init__(self, time=np.empty(0), data=np.empty((0, 1)), meta=None, columns=None, y=None):
        if meta is None:
            meta = dict()
        if columns is None:
            columns = []
        self.meta = meta
        if len(data.shape) == 1:
            self.values = data.reshape((data.shape[0], 1))  # to be consistent with pandas
        else:
            self.values = data
        self.time = time
        self.columns = columns
        self.y = y

    def view(self, time_range):
        return SpwcVariable(self.time[time_range], self.values[time_range], self.meta, self.columns, self.y)

    def __eq__(self, other: 'SpwcVariable') -> bool:
        return self.meta == other.meta and \
               self.columns == other.columns and \
               len(self.time) == len(other.time) and \
               np.all(self.time == other.time) and \
               np.all(self.values == other.values)

    def __len__(self):
        return len(self.time)

    def __getitem__(self, key):
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
        if datetime_index:
            time = pds.to_datetime(self.time, unit='s')
        else:
            time = self.time
        return pds.DataFrame(index=time, data=self.values, columns=self.columns, copy=True)

    def plot(self, *args, **kwargs):
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
    def from_dataframe(df: pds.DataFrame) -> 'SpwcVariable':
        if hasattr(df.index[0], 'timestamp'):
            time = np.array([d.timestamp() for d in df.index])
        else:
            time = df.index.values
        return SpwcVariable(time, df.values, {}, [c for c in df.columns])


def from_dataframe(df: pds.DataFrame) -> SpwcVariable:
    return SpwcVariable.from_dataframe(df)


def to_dataframe(var: SpwcVariable, datetime_index=False) -> pds.DataFrame:
    return SpwcVariable.to_dataframe(var, datetime_index)


def merge(variables: List[SpwcVariable]) -> Optional[SpwcVariable]:
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
        return SpwcVariable(columns=variables[0].columns, meta=variables[0].meta, y=variables[0].y)

    overlaps = [np.where(current.time >= nxt.time[0])[0][0] if current.time[-1] >= nxt.time[0] else -1 for current, nxt
                in
                zip(sorted_var_list[:-1], sorted_var_list[1:])]

    dest_len = int(np.sum(
        [overlap if overlap != -1 else len(r.time) for overlap, r in zip(overlaps, sorted_var_list[:-1])]))
    dest_len += len(sorted_var_list[-1].time)

    time = np.zeros(dest_len)
    data = np.zeros((dest_len, sorted_var_list[0].values.shape[1])) if len(
        sorted_var_list[0].values.shape) == 2 else np.zeros(dest_len)

    pos = 0
    for r, overlap in zip(sorted_var_list, overlaps + [-1]):
        frag_len = len(r.time) if overlap == -1 else overlap
        time[pos:pos + frag_len] = r.time[0:frag_len]
        data[pos:pos + frag_len] = r.values[0:frag_len]
        pos += frag_len
    return SpwcVariable(time, data, sorted_var_list[0].meta, sorted_var_list[0].columns, y=sorted_var_list[0].y)
