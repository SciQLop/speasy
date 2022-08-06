from speasy import SpeasyVariable
from .cache import CacheItem
from typing import Union, Callable, List, Tuple
from speasy.core.datetime_range import DateTimeRange
from .. import make_utc_datetime
from speasy.products.variable import merge as merge_variables
from speasy.core.inventory.indexes import ParameterIndex
from datetime import datetime, timedelta, timezone
from functools import wraps
import logging
import math
from ._instance import _cache

log = logging.getLogger(__name__)

CACHE_ALLOWED_KWARGS = ['disable_proxy', 'disable_cache']


def lower_hour_bound(dt: datetime, factor: int):
    return math.floor(dt.hour / factor) * factor


def upper_hour_bound(dt: datetime, factor: int):
    offsef = int(bool(dt - dt.replace(minute=0, second=0, microsecond=0)))
    return max(math.ceil((dt.hour + offsef) / factor), 1) * factor


def round_for_cache(dt_range: DateTimeRange, fragment_hours: int):
    start_time = dt_range.start_time.replace(hour=lower_hour_bound(dt_range.start_time, fragment_hours), minute=0,
                                             second=0, microsecond=0)
    stop_time = dt_range.stop_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        hours=upper_hour_bound(dt_range.stop_time, fragment_hours))
    return DateTimeRange(start_time, stop_time)


def is_up_to_date(item: CacheItem, version):
    return (item.version is None) or (item.version >= version)


def group_contiguous_fragments(fragments, duration):
    merged = []
    if len(fragments):
        merged = [[fragments[0]]]
        for fragment in fragments[1:]:
            if (merged[-1][-1] + duration * 1.01) > fragment:
                merged[-1].append(fragment)
            else:
                merged.append([fragment])
    return merged


def default_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    return f"{prefix}/{product}/{start_time}"


def product_name(product: str or ParameterIndex):
    if type(product) is str:
        return product
    elif isinstance(product, ParameterIndex):
        return product.uid
    else:
        raise TypeError(f'Product must either be str or ParameterIndex got {type(product)}')


class _Cacheable:
    def __init__(self, prefix, cache_instance=_cache, start_time_arg='start_time', stop_time_arg='stop_time',
                 version=None,
                 fragment_hours=lambda x: 1, cache_margins=1.2, leak_cache=False, entry_name=default_cache_entry_name):
        self.start_time_arg = start_time_arg
        self.stop_time_arg = stop_time_arg
        self.version = (lambda x, y: 0) if version is None else version
        self.fragment_hours = fragment_hours
        self.cache_margins = cache_margins
        self.cache = cache_instance
        self.prefix = prefix
        self.leak_cache = leak_cache
        self.entry_name = entry_name

    def add_to_cache(self, variable: SpeasyVariable or None, fragments, product, fragment_duration_hours, version,
                     **kwargs) -> SpeasyVariable or None:
        if variable is not None:
            for fragment in fragments:
                key = self.entry_name(self.prefix, product, fragment.isoformat(), **kwargs)
                log.debug(f"add {key} into cache")
                self.cache[key] = CacheItem(variable[fragment:fragment + timedelta(hours=fragment_duration_hours)],
                                            version)
        return variable

    def get_from_cache(self, fragment, product, version, **kwargs):
        key = self.entry_name(self.prefix, product, fragment.isoformat(), **kwargs)
        if key in self.cache:
            entry = self.cache[key]
            if is_up_to_date(entry, version):
                log.debug(f"Found {key} inside cache")
                return entry.data
            log.debug(f"Found outdated {key} inside cache")
        else:
            log.debug(f"{key} not found inside cache")
        return None

    def fragment_list(self, product, dt_range) -> Tuple[int, List[datetime]]:
        fragment_hours = self.fragment_hours(product)
        cache_dt_range = round_for_cache(dt_range * self.cache_margins, fragment_hours)
        dt = timedelta(hours=fragment_hours)
        fragments = [cache_dt_range.start_time + i * dt for i in range(math.ceil(cache_dt_range.duration / dt))]
        tend = cache_dt_range.start_time
        while tend < cache_dt_range.stop_time:
            fragments.append(tend)
            tend += timedelta(hours=fragment_hours)
        return fragment_hours, fragments

    def get_fragments_from_cache(self, fragments: List[str], product: str, version, **kwargs):
        data_fragments = []
        with self.cache.transact():
            for fragment in fragments:
                data_fragments.append(self.get_from_cache(fragment, product, version, **kwargs))
        return data_fragments


class Cacheable(object):
    def __init__(self, prefix, cache_instance=_cache, start_time_arg='start_time', stop_time_arg='stop_time',
                 version=None,
                 fragment_hours=lambda x: 1, cache_margins=1.2, leak_cache=False, entry_name=default_cache_entry_name):
        self._cache = _Cacheable(prefix, cache_instance=cache_instance, start_time_arg=start_time_arg,
                                 stop_time_arg=stop_time_arg,
                                 version=version,
                                 fragment_hours=fragment_hours, cache_margins=cache_margins, leak_cache=leak_cache,
                                 entry_name=entry_name)

    def __call__(self, get_data):
        @wraps(get_data)
        def wrapped(wrapped_self, product, start_time, stop_time, **kwargs):
            product = product_name(product)
            version = self._cache.version(wrapped_self, product)
            dt_range = DateTimeRange(start_time, stop_time)
            if kwargs.pop("disable_cache", False):
                return get_data(wrapped_self, product=product, start_time=dt_range.start_time,
                                stop_time=dt_range.stop_time, **kwargs)

            fragment_hours, fragments = self._cache.fragment_list(product, dt_range)
            fragment_duration = timedelta(hours=fragment_hours)
            data = self._cache.get_fragments_from_cache(fragments=fragments, product=product, version=version,
                                                        **kwargs)
            missing_fragments = group_contiguous_fragments(
                [fragment for data, fragment in zip(data, fragments) if data is None],
                duration=fragment_duration)

            data += \
                list(filter(lambda d: d is not None, [
                    self._cache.add_to_cache(
                        get_data(
                            wrapped_self, product=product, start_time=fragment_group[0],
                            stop_time=fragment_group[-1] + fragment_duration, **kwargs),
                        fragments=fragment_group, product=product, fragment_duration_hours=fragment_hours,
                        version=version, **kwargs)
                    for fragment_group
                    in missing_fragments]))

            if len(data):
                return merge_variables(data)[dt_range.start_time:dt_range.stop_time]
            return None

        if self._cache.leak_cache:
            wrapped.cache = self._cache.cache
        return wrapped
