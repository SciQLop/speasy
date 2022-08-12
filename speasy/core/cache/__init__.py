from .cache import Cache, CacheItem
from ._function_cache import CacheCall
from ._providers_caches import CACHE_ALLOWED_KWARGS, Cacheable, UnversionedProviderCache
from ._instance import _cache


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
