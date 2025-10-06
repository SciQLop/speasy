from typing import Union
from datetime import datetime, timezone, timedelta

import diskcache as dc
from .version import str_to_version, version_to_str, Version
from speasy.config import cache as cache_cfg
from contextlib import ExitStack, contextmanager

cache_version = str_to_version("3.0")


class CacheItem:
    def __init__(self, data, version, lifetime=None):
        self.data = data
        self.version = version
        if lifetime is not None and isinstance(lifetime, (float, int)):
            lifetime = timedelta(seconds=lifetime)
        self.lifetime = lifetime
        self.created = datetime.now(tz=timezone.utc)

    def bump_creation_time(self) -> "CacheItem":
        self.created = datetime.now(tz=timezone.utc)
        return self

    def __setstate__(self, state):
        self.data = state["data"]
        self.version = state["version"]
        self.lifetime = state.get("lifetime", None)
        self.created = state.get("created", datetime.now(tz=timezone.utc))

    def is_expired(self) -> bool:
        if isinstance(self.lifetime, timedelta):
            return datetime.now(tz=timezone.utc) > (self.created + self.lifetime)
        else:
            return False


class Cache:
    __slots__ = ['cache_file', '_data', 'cache_type']

    def __init__(self, cache_path: str = "", cache_type='Cache'):
        cache_path = f"{cache_path}/{cache_type}"
        if cache_type == 'Fanout':
            self._data = dc.FanoutCache(cache_path, shards=8, size_limit=cache_cfg.size())
        elif cache_type == 'Cache':
            self._data = dc.Cache(cache_path, size_limit=cache_cfg.size())
        else:
            raise ValueError(f"Unimplemented cache type: {cache_type}")

        self.cache_type = cache_type
        self._data.stats(enable=True, reset=True)
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
        hit, miss = self._data.stats()
        return {
            "hit": hit,
            "misses": miss,
        }

    def __len__(self):
        return len(self._data)

    def __del__(self):
        self._data.close()

    def keys(self):
        return list(self._data)

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def set(self, key, value, expire=None):
        self._data.set(key, value, expire=expire)

    def add(self, key, value, expire=None):
        return self._data.add(key, value, expire=expire)

    def get(self, key, default_value=None):
        return self._data.get(key, default_value)

    def incr(self, key, delta=1, default=0):
        return self._data.incr(key, delta, default=default)

    def drop(self, key):
        self._data.delete(key)

    @contextmanager
    def transact(self):
        if self.cache_type != 'Fanout':
            with self._data.transact():
                yield
        else:
            with ExitStack():
                yield

    @contextmanager
    def lock(self, key: str):
        lock = dc.Lock(self._data, key)
        lock.acquire()
        try:
            yield lock
        finally:
            lock.release()
