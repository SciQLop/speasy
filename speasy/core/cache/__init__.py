from typing import Union
import re
from .cache import Cache, CacheItem
from ._function_cache import CacheCall
from ._providers_caches import CACHE_ALLOWED_KWARGS, Cacheable, UnversionedProviderCache
from ._instance import _cache
import logging

log = logging.getLogger(__name__)


def cache_len():
    """Return the number of items in the cache"""
    return len(_cache)


def cache_disk_size():
    """Return the size of the cache on disk"""
    return _cache.disk_size()


def stats():
    return _cache.stats()


def entries():
    """Return all cache entries as a list of keys

    Returns
    -------
    list
        A list of all cache keys
    """
    return _cache.keys()


def add_item(key, item, expires=None):
    """Add an item to the cache with an optional expiration time in seconds

    Parameters
    ----------
    key : str
        The key under which the item will be stored
    item : any
        The item to be stored
    expires : int, optional
        The expiration time in seconds, by default None (no expiration)
    """
    _cache.set(key, item, expires)


def drop_item(key):
    """Drop an item from the cache by key

    Parameters
    ----------
    key : str
        The key of the item to be dropped
    """
    _cache.drop(key)


def get_item(key, default_value=None):
    """Get an item from the cache by key

    Parameters
    ----------
    key : str
        The key of the item to be retrieved
    default_value : any, optional
        The default value to return if the key does not exist, by default None

    Returns
    -------
    any
        The item stored under the key or the default value if the key does not exist
    """
    return _cache.get(key, default_value)


def drop_matching_entries(pattern: Union[str, re.Pattern]):
    """Drop all cache entries that match a given pattern

    Parameters
    ----------
    pattern : str or re.Pattern
        The pattern to match cache keys against
    """
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    for key in filter(pattern.match, _cache.keys()):
        log.debug(f"Dropping cache entry {key}")
        _cache.drop(key)
