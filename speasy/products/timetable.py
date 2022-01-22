from speasy.core.datetime_range import DateTimeRange
from typing import List
from speasy.core import all_of_type, listify


def _all_are_datetime_ranges(dt_list):
    return all_of_type(dt_list, DateTimeRange)


class TimeTable:
    """A TimeTable is basically a collection of DateTimeRange

    """
    __slots__ = ['name', 'meta', '_storage']

    def __init__(self, name: str, meta: dict = None, dt_ranges: List[DateTimeRange] = None):
        self.name = name
        self.meta = meta or {}
        self._storage = dt_ranges or []
        if not _all_are_datetime_ranges(self._storage):
            raise TypeError(f"You must provide a list of {DateTimeRange}")

    def __getitem__(self, index):
        return self._storage[index]

    def __len__(self):
        return len(self._storage)

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

    def __repr__(self):
        return f"""<TimeTable: {self.name}>"""
