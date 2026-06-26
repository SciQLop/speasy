"""Fallback cache backend used when ``pysciqlop_cache`` cannot be imported.

The real backend is a compiled extension and is unavailable on some platforms
(notably WASM/Pyodide, where there is no pure-Python wheel). This drop-in
replacement mimics the small subset of the ``pysciqlop_cache`` API that Speasy
uses, but stores nothing: every lookup misses. Caching is thereby transparently
disabled rather than crashing at import time.

A lightweight in-memory backend could replace this later (e.g. for WASM64)
without touching the call sites.
"""
from contextlib import contextmanager


class _NoopStore:
    """A cache/index that never stores anything and always reports a miss."""

    def __init__(self, *args, **kwargs):
        pass

    # --- key / value access ---
    def get(self, key, default=None):
        return default

    def set(self, key, value, expire=None, tag=None):
        pass

    def add(self, key, value, expire=None, tag=None):
        # Nothing is stored, so the slot was always free: "adding" succeeds.
        return True

    def incr(self, key, delta=1, default=0):
        return default + delta

    def delete(self, key):
        return False

    def pop(self, key, default=None):
        return default

    def __getitem__(self, key):
        raise KeyError(key)

    def __setitem__(self, key, value):
        pass

    def __contains__(self, key):
        return False

    def __len__(self):
        return 0

    def __iter__(self):
        return iter(())

    # --- maintenance / stats ---
    def clear(self):
        pass

    def reset_stats(self):
        pass

    def stats(self):
        return {"hits": 0, "misses": 0}

    def volume(self):
        return 0

    def evict_tag(self, tag):
        return 0

    def expire(self):
        return 0

    @contextmanager
    def transact(self, key=None):
        yield


# The Speasy wrapper treats Cache, FanoutCache and Index uniformly enough that a
# single no-op store satisfies all three.
Cache = _NoopStore
FanoutCache = _NoopStore
Index = _NoopStore


class Lock:
    def __init__(self, cache, key, *args, **kwargs):
        pass

    def acquire(self, *args, **kwargs):
        return True

    def release(self, *args, **kwargs):
        return True
