from typing import List, Callable, Optional, Union

from ..common.datetime_range import DateTimeRange
from ..common import make_utc_datetime
import diskcache as dc
from ..common.variable import SpwcVariable
from ..common.variable import merge as merge_variables
from datetime import datetime, timedelta, timezone
from .version import str_to_version, version_to_str, Version
from ..config import cache_size
from functools import wraps

cache_version = str_to_version("1.1")


class CacheItem:
    def __init__(self, data, version):
        self.data = data
        self.version = version


class Cache:
    __slots__ = ['cache_file', '_data']

    def __init__(self, cache_path: str = ""):
        self._data = dc.FanoutCache(cache_path, shards=8, size_limit=int(float(cache_size.get())))
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

    def keys(self):
        return [item for item in self._data]

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def set(self, key, value, expire=None):
        self._data.set(key, value, expire=expire)



