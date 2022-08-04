from speasy import SpeasyVariable
from .cache import Cache, CacheItem
from speasy.config import cache_path
from typing import Union, Callable, List
from speasy.core.datetime_range import DateTimeRange
from .. import make_utc_datetime
from speasy.products.variable import merge as merge_variables
from speasy.core.inventory.indexes import ParameterIndex
from datetime import datetime, timedelta, timezone
from functools import wraps
import inspect
import logging
import base64

log = logging.getLogger(__name__)
_cache = Cache(cache_path.get())
CACHE_ALLOWED_KWARGS = ['disable_proxy', 'disable_cache']


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


def product_name(product: str or ParameterIndex):
    if type(product) is str:
        return product
    elif isinstance(product, ParameterIndex):
        return product.uid
    else:
        raise TypeError(f'Product must either be str or ParameterIndex got {type(product)}')


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

    def add_to_cache(self, variable: SpeasyVariable, fragments, product, fragment_duration_hours, version, **kwargs):
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

    def get_fragments_from_cache(self, fragments: List[str], product: str, version, **kwargs):
        data_fragments = []
        with self.cache.transact():
            for fragment in fragments:
                data_fragments.append(self.get_from_cache(fragment, product, version, **kwargs))
        return data_fragments

    def __call__(self, get_data):
        @wraps(get_data)
        def wrapped(wrapped_self, product, start_time, stop_time, **kwargs):
            product = product_name(product)
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
            result = []
            contiguous_fragments = []
            fragments_from_cache = self.get_fragments_from_cache(fragments=fragments, product=product, version=version,
                                                                 **kwargs)
            for data, fragment in zip(fragments_from_cache, fragments):
                if data is None:
                    contiguous_fragments.append(fragment)
                else:
                    result.append(data)
                    if len(contiguous_fragments):
                        data = get_data(wrapped_self, product=product, start_time=contiguous_fragments[0],
                                        stop_time=contiguous_fragments[-1] + timedelta(hours=fragment_hours), **kwargs)
                        self.add_to_cache(variable=data, fragments=contiguous_fragments, product=product,
                                          fragment_duration_hours=fragment_hours, version=version, **kwargs)
                        contiguous_fragments = []
                        if data is not None:
                            result.append(data)

            if len(contiguous_fragments):
                data = get_data(wrapped_self, product=product, start_time=contiguous_fragments[0],
                                stop_time=contiguous_fragments[-1] + timedelta(hours=fragment_hours), **kwargs)
                self.add_to_cache(data, contiguous_fragments, product, fragment_hours, version, **kwargs)
                if data is not None:
                    result.append(data)
            if len(result):
                return merge_variables(result)[dt_range.start_time:dt_range.stop_time]
            return None

        if self.leak_cache:
            wrapped.cache = self.cache
        return wrapped


def make_key_from_args(*args, **kwargs):
    key = list(map(str, args))
    key += list(map(lambda k: str(k) + "=" + str(kwargs[k]), sorted(kwargs.keys())))
    result = ','.join(key)
    return base64.b64encode(result.encode()).decode()


class CacheCall(object):
    def __init__(self, cache_retention=60 * 15, is_pure=False, cache_instance=_cache):
        self.cache_retention = cache_retention
        self.cache = cache_instance
        self.is_methode = False
        self.is_pure = is_pure

    def add_to_cache(self, cache_entry, value):
        if value is not None:
            self.cache.set(cache_entry, value, expire=self.cache_retention)
        return value

    def get_from_cache(self, cache_entry):
        return self.cache.get(cache_entry, None)

    def __call__(self, function: Callable):
        spec = inspect.getfullargspec(function)
        if len(spec.args) and 'self' == spec.args[0]:
            self.is_methode = True
        if self.is_pure:
            cache_entry_prefix = f"__internal__/CacheCall/{function.__module__}/{function.__qualname__}"
        else:
            cache_entry_prefix = f"__internal__/CacheCall/{hash(function)}"

        @wraps(function)
        def wrapped(*args, disable_cache=False, force_refresh=False, **kwargs):
            args_to_hash = args[1:] if self.is_methode and self.is_pure else args
            cache_entry = cache_entry_prefix + "/" + make_key_from_args(*args_to_hash, **kwargs)
            if disable_cache:
                return function(*args, **kwargs)
            if force_refresh:
                return self.add_to_cache(cache_entry, function(*args, **kwargs))
            else:
                return self.get_from_cache(cache_entry) or self.add_to_cache(cache_entry, function(*args, **kwargs))

        return wrapped
