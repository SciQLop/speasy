from math import nan

import numpy as np
import pandas as pds
from datetime import datetime
from typing import List, Any
from urllib.request import urlopen
import os


class SpwcVariable(object):
    __slots__ = ['meta', 'time', 'data', 'columns']

    def __init__(self, time=np.empty(0), data=np.empty(0), meta={}, columns=[]):
        self.meta = meta
        self.time = time
        self.data = data
        self.columns = columns

    def view(self, range):
        return SpwcVariable(self.time[range], self.data[range], self.meta)

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


def load_csv(filename: str):
    if '://' not in filename:
        filename = f"file://{os.path.abspath(filename)}"
    with urlopen(filename) as csv:
        line = csv.readline().decode()
        meta = {}
        columns = []
        while line[0] == '#':
            if ':' in line:
                key, value = line[1:].split(':', 1)
                meta[key.strip()] = value.strip()
            line = csv.readline().decode()
        data = pds.read_csv(csv, comment='#', delim_whitespace=True).values.transpose()
        time, data = data[0], data[1:].transpose()
        if 'DATA_COLUMNS' in meta:
            columns = [col.strip() for col in meta['DATA_COLUMNS'].split(',')[1:]]
        return SpwcVariable(time, data, meta, columns)


def from_dataframe(df: pds.DataFrame) -> SpwcVariable:
    if hasattr(df.index[0], 'timestamp'):
        time = np.array([d.timestamp() for d in df.index])
    else:
        time = df.index.values
    return SpwcVariable(time, df.values, {}, [c for c in df.columns])


def merge(variables: List[SpwcVariable]):
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
        return SpwcVariable()

    overlaps = [np.where(current.time >= nxt.time[0])[0][0] if current.time[-1] >= nxt.time[0] else -1 for current, nxt
                in
                zip(sorted_var_list[:-1], sorted_var_list[1:])]

    dest_len = int(np.sum(
        [overlap if overlap != -1 else len(r.time) for overlap, r in zip(overlaps, sorted_var_list[:-1])]))
    dest_len += len(sorted_var_list[-1].time)

    time = np.zeros(dest_len)
    data = np.zeros((dest_len, sorted_var_list[0].data.shape[1])) if len(
        sorted_var_list[0].data.shape) == 2 else np.zeros(dest_len)

    pos = 0
    for r, overlap in zip(sorted_var_list, overlaps + [-1]):
        frag_len = len(r.time) if overlap == -1 else overlap
        time[pos:pos + frag_len] = r.time[0:frag_len]
        data[pos:pos + frag_len] = r.data[0:frag_len]
        pos += frag_len
    return SpwcVariable(time, data, sorted_var_list[0].meta)
