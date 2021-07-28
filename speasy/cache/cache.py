from typing import Union

import diskcache as dc
from .version import str_to_version, version_to_str, Version
from ..config import cache_size

cache_version = str_to_version("1.1")


class CacheItem:
    def __init__(self, data, version):
        self.data = data
        self.version = version


class Cache:
    __slots__ = ['cache_file', '_data', '_hit', '_miss']

    def __init__(self, cache_path: str = ""):
        self._data = dc.FanoutCache(cache_path, shards=8, size_limit=int(float(cache_size.get())))
        self._hit = 0
        self._miss = 0
        if self.version < cache_version:
            self._data.clear()
            self.version = cache_version

    @property
    def version(self):
        return str_to_version(self._data.get("cache/version", default="0.0.0"))

    @version.setter
    def version(self, v: Union[str, Version]):
        self._data["cache/version"] = v if type(v) is str else version_to_str(v)

    def disk_size(self):
        return self._data.volume()

    def stats(self):
        return {
            "hit": self._hit,
            "misses": self._miss
        }

    def __len__(self):
        return len(self._data)

    def __del__(self):
        pass

    def keys(self):
        return list(self._data)

    def __contains__(self, item):
        if item in self._data:
            self._hit += 1
            return True
        self._miss += 1
        return False

    def __getitem__(self, key):
        if key in self._data:
            self._hit += 1
        else:
            self._miss += 1
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def set(self, key, value, expire=None):
        self._data.set(key, value, expire=expire)

    def get(self, key, default_value=None):
        return self._data.get(key, default_value)
