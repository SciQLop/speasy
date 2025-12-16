import base64
import inspect
from datetime import timedelta
from functools import wraps
from typing import Callable, Optional

from ._instance import _cache
from .cache import CacheItem


def make_key_from_args(*args, **kwargs):
    key = list(map(str, args))
    key += list(map(lambda k: str(k) + "=" + str(kwargs[k]), sorted(kwargs.keys())))
    result = ','.join(key)
    return base64.b64encode(result.encode()).decode()


class CacheCall(object):
    def __init__(self, cache_retention=60 * 15, is_pure=False, cache_instance=_cache, version=1, leak_cache=False):
        from ..platform import is_running_on_wasm
        if type(cache_retention) is timedelta:
            cache_retention = cache_retention.total_seconds()
        self.cache_retention = cache_retention
        self.cache = cache_instance
        self.is_methode = False
        self.is_pure = is_pure
        self.version = version
        self._cache_entry_prefix: Optional[str] = None
        self._leak_cache = leak_cache
        self._disable_cache = is_running_on_wasm()

    def add_to_cache(self, cache_entry, value):
        if value is not None:
            self.cache.set(cache_entry,
                           CacheItem(value, version=self.version, lifetime=timedelta(seconds=self.cache_retention)))
        return value

    def get_from_cache(self, cache_entry, prefer_cache=False):
        entry = self.cache.get(cache_entry, None)
        if isinstance(entry, CacheItem):
            if (entry.version == self.version) and (not entry.is_expired() or prefer_cache):
                return entry.data
        else:
            return entry
        return None

    def drop_entries(self):
        if self._cache_entry_prefix is not None:
            self.cache.drop_matching_entries(f"^{self._cache_entry_prefix}/.*$")

    def _analyse_function(self, function: Callable):
        spec = inspect.getfullargspec(function)
        if len(spec.args) and 'self' == spec.args[0]:
            self.is_methode = True
        if self.is_pure:
            self._cache_entry_prefix = f"__internal__/CacheCall/{function.__module__}/{function.__qualname__}"
        else:
            self._cache_entry_prefix = f"__internal__/CacheCall/{hash(function)}"
        if rtype := spec.annotations.get('return', None):
            if rtype in [bool, int, float, str]:
                self._disable_cache = False

    def __call__(self, function: Callable):
        self._analyse_function(function)

        @wraps(function)
        def wrapped(*args, disable_cache=False, force_refresh=False, prefer_cache=False, **kwargs):
            args_to_hash = args[1:] if self.is_methode and self.is_pure else args
            cache_entry = self._cache_entry_prefix + "/" + make_key_from_args(*args_to_hash, **kwargs)
            if self._disable_cache or disable_cache:
                return function(*args, **kwargs)
            if force_refresh:
                return self.add_to_cache(cache_entry, function(*args, **kwargs))
            else:
                return self.get_from_cache(cache_entry, prefer_cache=prefer_cache) or self.add_to_cache(cache_entry,
                                                                                                        function(*args,
                                                                                                                 **kwargs))

        setattr(wrapped, "drop_entries", self.drop_entries)
        if self._leak_cache:
            setattr(wrapped, "cache", self.cache)
        return wrapped
