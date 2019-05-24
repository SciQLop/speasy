from math import nan

import numpy as np
import pandas as pds
from typing import List, Any


class SpwcVariable(object):
    __slots__ = ['meta', 'time', 'data']

    def __init__(self, time=np.empty(0), data=np.empty(0), meta={}):
        self.meta = meta
        self.time = time
        self.data = data


def load_csv(filename: str):
    with open(filename) as csv:
        line = csv.readline()
        meta = {}
        while line[0] == '#':
            if ':' in line:
                key, value = line[1:].split(':', 1)
                meta[key.strip()] = value.strip()
            line = csv.readline()
        data = pds.read_csv(csv, comment='#', delim_whitespace=True).values.transpose()
        time, data = data[0], data[1:].transpose()
        return SpwcVariable(time, data, meta)


def merge(variables: List[SpwcVariable]):
    ranges = [(v.time[0], v.time[-1], v) if len(v.time) else (0., 0., v) for v in variables]
    ranges.sort(key=lambda t: t[0])
    # drop empty vars
    while len(ranges) and ranges[0][0] == 0.:
        del ranges[0]

    # drop variables covered by previous ones
    for prev, current in zip(ranges[:-1], ranges[1:]):
        if prev[1] >= current[1]:
            ranges.remove(current)

    # drop variables covered by next ones
    for current, nxt in zip(ranges[:-1], ranges[1:]):
        if nxt[0] == current[0] and nxt[1] >= current[1]:
            ranges.remove(current)

    if len(ranges) == 0:
        return SpwcVariable()
    overlaps = [np.where(current[2].time >= nxt[0])[0][0] if current[1] >= nxt[0] else -1 for current, nxt in
                zip(ranges[:-1], ranges[1:])]
    dest_len = int(np.sum(
        [overlap if overlap != -1 else len(r[2].time) for overlap, r in zip(overlaps, ranges[:-1])]))
    dest_len += len(ranges[-1][2].time)
    time = np.zeros(dest_len)
    data = np.zeros((dest_len, ranges[0][2].data.shape[1])) if len(ranges[0][2].data.shape) == 2 else np.zeros(dest_len)
    pos = 0
    for r, overlap in zip(ranges, overlaps + [-1]):
        frag_len = len(r[2].time) if overlap == -1 else overlap
        time[pos:pos + frag_len] = r[2].time[0:frag_len]
        data[pos:pos + frag_len] = r[2].data[0:frag_len]
        pos += frag_len
    return SpwcVariable(time, data, ranges[0][2].meta)
