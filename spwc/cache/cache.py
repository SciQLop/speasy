import os
from pathlib import Path
from typing import List, Optional

import jsonpickle
from ..common.datetime_range import DateTimeRange
import diskcache as dc


class CacheEntry:

    dt_range: DateTimeRange
    data_entry: str

    __slots__ = ['dt_range', 'data_entry']

    def __init__(self, dt_range: DateTimeRange, data_entry: str):
        self.dt_range = dt_range
        self.data_entry = data_entry

    def __eq__(self, other):
        assert type(other) is CacheEntry
        return (self.dt_range == other.dt_range) and (self.data_entry == other.data_entry)

    @property
    def start_time(self):
        return self.dt_range.start_time

    @property
    def stop_time(self):
        return self.dt_range.stop_time

    def __getitem__(self, item):
        return self.start_time if item == 0 else self.stop_time

    def __contains__(self, item: object) -> bool:
        return item in self.dt_range

    def __lt__(self, other):
        return self.start_time < other.start_time

    def __gt__(self, other):
        return self.start_time > other.start_time


class Cache:
    __slots__ = ['cache_file', '_data']

    def __init__(self, cache_path: str = ""):
        self._data =  dc.Cache(cache_path)

    def __del__(self):
        pass

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, item):
        return self._data[item]

    def add_entry(self, product, entry, data):
        if product in self._data:
            self._data[product].append(entry)
        else:
            self._data[product] = [entry]
        self._data[entry.data_entry] = data

    def get_entries(self, parameter_id: str, dt_range: DateTimeRange) -> List[CacheEntry]:
        if parameter_id in self:
            entries = [entry for entry in self[parameter_id] if dt_range.intersect(entry.dt_range)]
            #return entries if len(entries) else None
            return entries
        else:
            return []

    def get_missing_ranges(self, parameter_id: str, dt_range: DateTimeRange) -> List[DateTimeRange]:
        hit_ranges = self.get_entries(parameter_id, dt_range)
        if hit_ranges:
            return dt_range - hit_ranges
        else:
            return [dt_range]

