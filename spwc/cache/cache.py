from typing import List, Callable, Optional, Union

from ..common.datetime_range import DateTimeRange
import diskcache as dc
import pandas as pds
from ..common.variable import SpwcVariable, from_dataframe
from ..common.variable import merge as merge_variables
from datetime import datetime, timedelta, timezone
from .version import str_to_version, version_to_str, Version

cache_version = str_to_version("1.0")


def _round(value: int, factor: int):
    return int(value / factor) * factor


def _round_for_cache(dt_range: DateTimeRange, fragment_hours: int):
    start_time = datetime(dt_range.start_time.year, dt_range.start_time.month, dt_range.start_time.day,
                          _round(dt_range.start_time.hour, fragment_hours),
                          tzinfo=dt_range.start_time.tzinfo)
    stop_time = datetime(dt_range.stop_time.year, dt_range.stop_time.month, dt_range.stop_time.day,
                         _round(dt_range.stop_time.hour, fragment_hours),
                         tzinfo=dt_range.stop_time.tzinfo)
    if stop_time != dt_range.stop_time:
        stop_time += timedelta(hours=fragment_hours)
    return DateTimeRange(start_time, stop_time)


def _change_tz(dt: Union[DateTimeRange, datetime], tz):
    if type(dt) is datetime:
        if tz != dt.tzinfo:
            return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond, tzinfo=tz)
        else:
            return dt
    elif type(dt) is DateTimeRange:
        return DateTimeRange(_change_tz(dt.start_time, tz), _change_tz(dt.stop_time, tz))
    else:
        raise TypeError()


class CacheItem:
    def __init__(self, data, version):
        self.data = data
        self.version = version


def _is_up_to_date(item: CacheItem, version):
    return (item.version is None) or (item.version >= version)


class Cache:
    __slots__ = ['cache_file', '_data']

    def __init__(self, cache_path: str = ""):
        self._data = dc.Cache(cache_path, size_limit=int(20e9))
        if self.version < cache_version:
            self._data.clear()
            self.version = cache_version

    @property
    def version(self):
        return str_to_version(self._data.get("cache/version", default="0.0.0"))

    @version.setter
    def version(self, v: Union[str, Version]):
        self._data["cache/version"] = v if type(v) is str else version_to_str(v)

    def __del__(self):
        pass

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def _add_to_cache(self, var: SpwcVariable, fragments: List[datetime], parameter_id: str, fragment_duration_hours=1,
                      version=None):
        if var is not None:
            for fragment in fragments:
                self._data[f"{parameter_id}/{fragment.isoformat()}"] = CacheItem(var[fragment:fragment + timedelta(
                    hours=fragment_duration_hours)], version)

    def _get_fragments(self, var: SpwcVariable, parameter_id: str, fragments: List[datetime],
                       request: Callable[[datetime, datetime], SpwcVariable], fragment_hours=1,
                       version=None) -> SpwcVariable:
        if len(fragments):
            new_var = request(fragments[0], fragments[-1] + timedelta(hours=fragment_hours))
            var = merge_variables([var, new_var])
            self._add_to_cache(new_var, fragments, parameter_id, fragment_hours, version)
        return var

    def set(self, key, value, expire=None):
        self._data.set(key, value, expire=expire)

    def get_data(self, parameter_id: str, dt_range: DateTimeRange,
                 request: Callable[[datetime, datetime], SpwcVariable], fragment_hours=1, version=None) -> Optional[
        SpwcVariable]:

        dt_range = _change_tz(dt_range, timezone.utc)
        cache_dt_range = _round_for_cache(dt_range * 1.2, fragment_hours)
        fragments = []
        tend = cache_dt_range.start_time
        while tend < cache_dt_range.stop_time:
            fragments.append(tend)
            tend += timedelta(hours=fragment_hours)
        result = None
        contiguous_fragments = []
        for fragment in fragments:
            key = f"{parameter_id}/{fragment.isoformat()}"
            if key in self._data:
                item = self._data[key]
                if item.data is not None and _is_up_to_date(item, version):
                    if len(contiguous_fragments):
                        result = self._get_fragments(result, parameter_id, contiguous_fragments, request,
                                                     fragment_hours, version)
                        contiguous_fragments = []
                    result = merge_variables([result, item.data])
                else:
                    contiguous_fragments.append(fragment)
            else:
                contiguous_fragments.append(fragment)
        if len(contiguous_fragments):
            result = self._get_fragments(result, parameter_id, contiguous_fragments, request, fragment_hours, version)
        if result is not None:
            return result[dt_range.start_time:dt_range.stop_time]
        return None
