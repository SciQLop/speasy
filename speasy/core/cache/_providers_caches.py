import logging
import math
from datetime import datetime, timedelta
from functools import wraps
from typing import List, Tuple

from speasy import SpeasyVariable
from speasy.core import progress_bar
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import ParameterIndex
from speasy.products.variable import merge as merge_variables, to_dictionary, from_dictionary
from ._instance import _cache
from .cache import CacheItem

log = logging.getLogger(__name__)

CACHE_ALLOWED_KWARGS = ['disable_cache']


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


def group_fragments_if(fragments, predicate):
    merged = []
    if len(fragments):
        merged = [[fragments[0]]]
        for fragment in fragments[1:]:
            if predicate(merged[-1][-1], fragment):
                merged[-1].append(fragment)
            else:
                merged.append([fragment])
    return merged


def group_contiguous_fragments(fragments, duration):
    return group_fragments_if(fragments, lambda previous, current: (previous + duration * 1.01) > current)


def default_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    return f"{prefix}/{product}/{start_time}"


def product_name(product: str or ParameterIndex):
    if type(product) is str:
        return product
    elif isinstance(product, ParameterIndex):
        return product.spz_uid()
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
                self.set_cache_entry(fragment, product,
                                     CacheItem(to_dictionary(
                                         variable[fragment:(fragment + timedelta(hours=fragment_duration_hours))]),
                                         version), **kwargs)
        return variable

    def set_cache_entry(self, fragment, product: str, entry, **kwargs):
        key = self.entry_name(self.prefix, product, fragment.isoformat(), **kwargs)
        log.debug(f"add {key} into cache")
        self.cache[key] = entry

    def get_cache_entry(self, fragment: datetime, product, **kwargs):
        key = self.entry_name(self.prefix, product, fragment.isoformat(), **kwargs)
        if key in self.cache:
            entry = self.cache[key]
            log.debug(f"Found {key} inside cache")
            return entry
        else:
            log.debug(f"{key} not found inside cache")
        return None

    def get_from_cache(self, fragment, product, version, **kwargs):
        entry = self.get_cache_entry(fragment, product, **kwargs)
        if entry is not None:
            if is_up_to_date(entry, version):
                try:
                    return from_dictionary(entry.data)
                except Exception as e:
                    log.warning(f"got an exception {e} while loading fragment {fragment} for {product}")
                    return None
            log.debug(f"Cache entry is outdated")
        return None

    def fragment_list(self, product, dt_range) -> Tuple[int, List[datetime]]:
        fragment_hours = self.fragment_hours(product)
        cache_dt_range = round_for_cache(dt_range * self.cache_margins, fragment_hours)
        dt = timedelta(hours=fragment_hours)
        fragments = [cache_dt_range.start_time + i * dt for i in range(math.ceil(cache_dt_range.duration / dt))]
        return fragment_hours, fragments

    def get_fragments_from_cache(self, fragments: List[datetime], product: str, version, **kwargs):
        data_fragments = []
        with self.cache.transact():
            for fragment in fragments:
                data_fragments.append(self.get_from_cache(fragment, product, version, **kwargs))
        return data_fragments

    def get_cache_entries(self, fragments: List[datetime], product: str, **kwargs):
        return [self.get_cache_entry(fragment, product, **kwargs) for fragment in fragments]


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
            data_chunks = self._cache.get_fragments_from_cache(fragments=fragments, product=product, version=version,
                                                               **kwargs)
            missing_fragments = group_contiguous_fragments(
                [fragment for f_data, fragment in zip(data_chunks, fragments) if f_data is None],
                duration=fragment_duration)

            data_chunks += [
                self._cache.add_to_cache(
                    get_data(
                        wrapped_self, product=product, start_time=fragment_group[0],
                        stop_time=fragment_group[-1] + fragment_duration, **kwargs),
                    fragments=fragment_group, product=product, fragment_duration_hours=fragment_hours,
                    version=version, **kwargs)
                for fragment_group
                in
                progress_bar(leave=False, desc="Downloading missing fragments from cache", **kwargs)(missing_fragments)]

            data_chunks = list(filter(lambda d: d is not None, data_chunks))

            if len(data_chunks):
                if len(data_chunks) == 1:
                    return data_chunks[0][dt_range.start_time:dt_range.stop_time].copy()
                if data_chunks[0] is not None:
                    data_chunks[0] = data_chunks[0][dt_range.start_time:]
                if data_chunks[-1] is not None:
                    data_chunks[-1] = data_chunks[-1][:dt_range.stop_time]
                return merge_variables(data_chunks)[dt_range.start_time:dt_range.stop_time]
            return None

        if self._cache.leak_cache:
            wrapped.cache = self._cache.cache
        return wrapped


class UnversionedProviderCache(object):
    def __init__(self, prefix, cache_instance=_cache, start_time_arg='start_time', stop_time_arg='stop_time',
                 fragment_hours=lambda x: 1, cache_margins=1.2, leak_cache=False, entry_name=default_cache_entry_name,
                 cache_retention=None):
        self._cache = _Cacheable(prefix, cache_instance=cache_instance, start_time_arg=start_time_arg,
                                 stop_time_arg=stop_time_arg,
                                 version=lambda x, y: datetime.utcnow().isoformat(),
                                 fragment_hours=fragment_hours, cache_margins=cache_margins, leak_cache=leak_cache,
                                 entry_name=entry_name)
        self.cache_retention = cache_retention or timedelta(days=14)

    def split_fragments(self, fragments, product, fragment_duration, **kwargs):
        entries = self._cache.get_cache_entries(fragments=fragments, product=product, **kwargs)
        missing_fragments = []
        data_chunks = []
        maybe_outdated_fragments = []
        for fragment, entry in zip(fragments, entries):
            if entry is None:
                missing_fragments.append(fragment)
            elif (entry.version + self.cache_retention) > datetime.utcnow():
                try:
                    data_chunks.append(from_dictionary(entry.data))
                except Exception as e:
                    missing_fragments.append(fragment)
                    log.warning(f"got an exception {e} while loading fragment {fragment} for {product}")
            else:
                maybe_outdated_fragments.append((fragment, entry))

        missing_fragments = group_contiguous_fragments(missing_fragments, duration=fragment_duration)
        # This is a deliberate choice here to group fragments in order to reduce requests count, the bet here is
        # that it costs less to asks for more data in one shot then doing several requests. To be more clear about
        # the issue here, grouping fragments implies choosing a date to compare for the whole group and by
        # construction each fragment inside the group is likely to have different date. So the safe choice is to
        # declare the whole group as old as the oldest element which leads to maybe updating some fragments inside
        # the group that were up-to-date.
        maybe_outdated_fragments = group_fragments_if(
            maybe_outdated_fragments,
            lambda previous, current: (previous[0] + fragment_duration * 1.01) > current[0])
        return data_chunks, maybe_outdated_fragments, missing_fragments

    def __call__(self, get_data):
        @wraps(get_data)
        def wrapped(wrapped_self, product, start_time, stop_time, **kwargs):
            product = product_name(product)
            dt_range = DateTimeRange(start_time, stop_time)
            if kwargs.pop("disable_cache", False):
                return get_data(wrapped_self, product=product, start_time=dt_range.start_time,
                                stop_time=dt_range.stop_time, **kwargs)

            fragment_hours, fragments = self._cache.fragment_list(product, dt_range)
            fragment_duration = timedelta(hours=fragment_hours)
            data_chunks, maybe_outdated_fragments, missing_fragments = self.split_fragments(fragments, product,
                                                                                            fragment_duration, **kwargs)
            data_chunks += \
                list(filter(lambda d: d is not None, [
                    self._cache.add_to_cache(
                        get_data(
                            wrapped_self, product=product, start_time=fragment_group[0],
                            stop_time=fragment_group[-1] + fragment_duration, **kwargs),
                        fragments=fragment_group, product=product, fragment_duration_hours=fragment_hours,
                        version=datetime.utcnow(), **kwargs)
                    for fragment_group
                    in progress_bar(leave=False, desc="Downloading missing fragments from cache", **kwargs)(
                        missing_fragments)]))

            for group in progress_bar(leave=False, desc="Checking if cache fragments are outdated", **kwargs)(
                maybe_outdated_fragments):
                oldest = max(group, key=lambda item: item[1].version)[1].version
                kwargs['if_newer_than'] = oldest
                data = get_data(wrapped_self, product=product, start_time=group[0][0],
                                stop_time=group[-1][0] + fragment_duration, **kwargs)
                if data is None:
                    for fragment, entry in group:
                        entry.version = datetime.utcnow()
                        self._cache.set_cache_entry(fragment, product, entry)
                        data_chunks.append(entry.data)
                else:
                    self._cache.add_to_cache(data, [item[0] for item in group], product,
                                             fragment_duration_hours=fragment_hours,
                                             version=datetime.now(), **kwargs)
                    data_chunks.append(data)

            if len(data_chunks):
                if len(data_chunks) == 1:
                    if data_chunks[0] is not None:
                        return data_chunks[0][dt_range.start_time:dt_range.stop_time].copy()
                    else:
                        return None
                if data_chunks[0] is not None:
                    data_chunks[0] = data_chunks[0][dt_range.start_time:]
                if data_chunks[-1] is not None:
                    data_chunks[-1] = data_chunks[-1][:dt_range.stop_time]
                return merge_variables(data_chunks)[dt_range.start_time:dt_range.stop_time]
            return None

        if self._cache.leak_cache:
            wrapped.cache = self._cache.cache
        return wrapped
