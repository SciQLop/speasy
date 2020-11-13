from spwc import SpwcVariable
from .cache import Cache, CacheItem
from ..config import cache_path
from typing import List, Callable, Optional, Union
from ..common.datetime_range import DateTimeRange
from ..common import make_utc_datetime
from ..common.variable import merge as merge_variables
from datetime import datetime, timedelta, timezone
from functools import wraps
import logging

log = logging.getLogger(__name__)
_cache = Cache(cache_path.get())


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


def _is_up_to_date(item: CacheItem, version):
    return (item.version is None) or (item.version >= version)


def _make_range(start_time, stop_time):
    dt_range = DateTimeRange(make_utc_datetime(start_time), make_utc_datetime(stop_time))
    return _change_tz(dt_range, timezone.utc)


def cache_len():
    return len(_cache)


def cache_disk_size():
    return _cache.disk_size()


def stats():
    return _cache.stats()


def entries():
    return _cache.keys()


def add_item(key, item, expires=None):
    _cache.set(key, item, expires)


def get_item(key, default_value=None):
    return _cache.get(key, default_value)


def default_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    return f"{prefix}/{product}/{start_time}"


class Cacheable(object):
    def __init__(self, prefix, cache_instance=_cache, start_time_arg='start_time', stop_time_arg='stop_time',
                 version=None,
                 fragment_hours=lambda x: 1, cache_margins=1.2, leak_cache=False, entry_name=default_cache_entry_name):
        self.start_time_arg = start_time_arg
        self.stop_time_arg = stop_time_arg
        self.version = version
        self.fragment_hours = fragment_hours
        self.cache_margins = cache_margins
        self.cache = cache_instance
        self.prefix = prefix
        self.leak_cache = leak_cache
        self.entry_name = entry_name

    def add_to_cache(self, variable: SpwcVariable, fragments, product, fragment_duration_hours, version, **kwargs):
        if variable is not None:
            for fragment in fragments:
                key = self.entry_name(self.prefix, product, fragment.isoformat(), **kwargs)
                log.debug(f"add {key} into cache")
                self.cache[key] = CacheItem(variable[fragment:fragment + timedelta(hours=fragment_duration_hours)],
                                            version)

    def get_from_cache(self, fragment, product, version, **kwargs):
        key = self.entry_name(self.prefix, product, fragment.isoformat(), **kwargs)
        if key in self.cache:
            entry = self.cache[key]
            if _is_up_to_date(entry, version):
                log.debug(f"Found {key} inside cache")
                return entry.data
            log.debug(f"Found outdated {key} inside cache")
        else:
            log.debug(f"{key} not found inside cache")
        return None

    def __call__(self, get_data):
        @wraps(get_data)
        def wrapped(wrapped_self, product, start_time, stop_time, **kwargs):
            version = self.version(wrapped_self, product) if self.version else 0
            dt_range = _make_range(start_time, stop_time)
            if kwargs.pop("disable_cache", False):
                return get_data(wrapped_self, product=product, start_time=dt_range.start_time,
                                stop_time=dt_range.stop_time, **kwargs)
            fragment_hours = self.fragment_hours(product)
            cache_dt_range = _round_for_cache(dt_range * self.cache_margins, fragment_hours)
            fragments = []
            tend = cache_dt_range.start_time
            while tend < cache_dt_range.stop_time:
                fragments.append(tend)
                tend += timedelta(hours=fragment_hours)
            result = None
            contiguous_fragments = []
            for fragment in fragments:
                data = self.get_from_cache(fragment=fragment, product=product, version=version, **kwargs)
                if data is None:
                    contiguous_fragments.append(fragment)
                else:
                    if len(contiguous_fragments):
                        result = get_data(wrapped_self, product=product, start_time=fragments[0],
                                          stop_time=fragments[-1] + timedelta(hours=fragment_hours), **kwargs)
                        self.add_to_cache(variable=result, fragments=contiguous_fragments, product=product,
                                          fragment_duration_hours=fragment_hours, version=version, **kwargs)
                        contiguous_fragments = []
                    result = merge_variables([result, data])
            if len(contiguous_fragments):
                result = get_data(wrapped_self, product=product, start_time=fragments[0],
                                  stop_time=fragments[-1] + timedelta(hours=fragment_hours), **kwargs)
                self.add_to_cache(result, contiguous_fragments, product, fragment_hours, version, **kwargs)
            if result is not None:
                return result[dt_range.start_time:dt_range.stop_time]
            return None

        if self.leak_cache:
            wrapped.cache = self.cache
        return wrapped
