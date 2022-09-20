import base64
import inspect
from datetime import timedelta
from functools import wraps
from typing import Callable

from ._instance import _cache


def make_key_from_args(*args, **kwargs):
    key = list(map(str, args))
    key += list(map(lambda k: str(k) + "=" + str(kwargs[k]), sorted(kwargs.keys())))
    result = ','.join(key)
    return base64.b64encode(result.encode()).decode()


class CacheCall(object):
    def __init__(self, cache_retention=60 * 15, is_pure=False, cache_instance=_cache):
        if type(cache_retention) is timedelta:
            cache_retention = cache_retention.total_seconds()
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
