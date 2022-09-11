from speasy.core.datetime_range import DateTimeRange
from .base_product import SpeasyProduct
from typing import List
from speasy.core import all_of_type, listify
import pandas as pds


def _all_are_datetime_ranges(dt_list):
    return all_of_type(dt_list, DateTimeRange)


class TimeTable(SpeasyProduct):
    """A TimeTable is basically a collection of DateTimeRange

    """
    __slots__ = ['name', 'meta', '_storage']

    def __init__(self, name: str, meta: dict = None, dt_ranges: List[DateTimeRange] = None):
        super().__init__()
        self.name = name
        self.meta = meta or {}
        self._storage = dt_ranges or []
        if not _all_are_datetime_ranges(self._storage):
            raise TypeError(f"You must provide a list of {DateTimeRange}")

    def __getitem__(self, index):
        return self._storage[index]

    def __len__(self):
        return len(self._storage)

    def __iter__(self):
        return self._storage.__iter__()

    def append(self, dt_range: DateTimeRange or List[DateTimeRange]):
        dt_range = listify(dt_range)
        if not _all_are_datetime_ranges(dt_range):
            raise TypeError(
                f"You must provide a {DateTimeRange} or a List of {DateTimeRange} instead of {type(dt_range)}")
        self._storage += dt_range

    def __iadd__(self, other: DateTimeRange or List[DateTimeRange]):
        self.append(other)
        return self

    def pop(self, index=-1):
        return self._storage.pop(index)

    def to_dataframe(self) -> pds.DataFrame:
        return pds.DataFrame(columns=['start_time', 'stop_time'], data=[(*r,) for r in self])

    def __repr__(self):
        return f"""<TimeTable: {self.name}>"""
