from typing import List, Callable, Optional, Union

from ..common.datetime_range import DateTimeRange
import diskcache as dc
import pandas as pds
from ..common.variable import SpwcVariable, from_dataframe
from ..common.variable import merge as merge_variables
from datetime import datetime, timedelta, timezone


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


class Cache:
    __slots__ = ['cache_file', '_data']

    def __init__(self, cache_path: str = ""):
        self._data = dc.Cache(cache_path, size_limit=int(20e9))

    def __del__(self):
        pass

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def _add_to_cache(self, var: SpwcVariable, fragments: List[datetime], parameter_id: str, fragment_duration_hours=1):
        if var is not None:
            for fragment in fragments:
                self._data[f"{parameter_id}/{fragment.isoformat()}"] = var[fragment:fragment + timedelta(
                    hours=fragment_duration_hours)]

    def _get_fragments(self, var: SpwcVariable, parameter_id: str, fragments: List[datetime],
                       request: Callable[[datetime, datetime], SpwcVariable], fragment_hours=1) -> SpwcVariable:
        if len(fragments):
            new_var = request(fragments[0], fragments[-1] + timedelta(hours=fragment_hours))
            var = merge_variables([var, new_var])
            self._add_to_cache(new_var, fragments, parameter_id, fragment_hours)
        return var

    def get_data(self, parameter_id: str, dt_range: DateTimeRange,
                 request: Callable[[datetime, datetime], SpwcVariable], fragment_hours=1, last_update=None) -> Optional[
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
            var = None
            if key in self._data:
                var = self._data[key]
                if isinstance(var, pds.DataFrame):  # convert any remaining DataFrame from previous releases
                    var = from_dataframe(var)
                if var is not None:
                    if len(contiguous_fragments):
                        result = self._get_fragments(result, parameter_id, contiguous_fragments, request,
                                                     fragment_hours)
                        contiguous_fragments = []
                    result = merge_variables([result, var])
                else:
                    contiguous_fragments.append(fragment)
            else:
                contiguous_fragments.append(fragment)
        if len(contiguous_fragments):
            result = self._get_fragments(result, parameter_id, contiguous_fragments, request, fragment_hours)
        if result is not None:
            return result[dt_range.start_time:dt_range.stop_time]
        return None
