from typing import Union

import diskcache as dc
from .version import str_to_version, version_to_str, Version
from speasy.config import cache as cache_cfg
from contextlib import ExitStack

cache_version = str_to_version("2.0")


class CacheItem:
    def __init__(self, data, version):
        self.data = data
        self.version = version


class Cache:
    __slots__ = ['cache_file', '_data', '_hit', '_miss', 'cache_type']

    def __init__(self, cache_path: str = "", cache_type='Cache'):
        cache_path = f"{cache_path}/{cache_type}"
        if cache_type == 'Fanout':
            self._data = dc.FanoutCache(cache_path, shards=8, size_limit=cache_cfg.size())
        elif cache_type == 'Cache':
            self._data = dc.Cache(cache_path, size_limit=cache_cfg.size())
        else:
            raise ValueError(f"Unimplemented cache type: {cache_type}")

        self.cache_type = cache_type
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
        self._data.close()

    def keys(self):
        return list(self._data)

    def __contains__(self, item):
        with self.transact():
            if item in self._data:
                self._hit += 1
                return True
            self._miss += 1
            return False

    def __getitem__(self, key):
        with self.transact():
            if key in self._data:
                self._hit += 1
            else:
                self._miss += 1
            return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def set(self, key, value, expire=None):
        with self.transact():
            self._data.set(key, value, expire=expire)

    def get(self, key, default_value=None):
        with self.transact():
            return self._data.get(key, default_value)

    def drop(self, key):
        with self.transact():
            self._data.delete(key)

    def transact(self):
        if self.cache_type != 'Fanout':
            return self._data.transact()
        else:
            return ExitStack()
