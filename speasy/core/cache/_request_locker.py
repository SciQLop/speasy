from contextlib import contextmanager
from ._instance import _cache
from time import sleep
from datetime import datetime, timezone
from threading import get_native_id
from typing import Optional


class PendingRequest:
    def __init__(self):
        self._start_time = datetime.now(tz=timezone.utc)
        self._pid = get_native_id()

    @property
    def elapsed_time(self):
        return datetime.now(tz=timezone.utc) - self._start_time

    def has_timed_out(self, timeout: int) -> bool:
        return int(self.elapsed_time.total_seconds()) >= timeout

    @property
    def pid(self):
        return self._pid

    @property
    def is_from_current_thread(self):
        return self._pid == get_native_id()


def _is_locked(key: str, timeout: int = 30) -> bool:
    """Check if a cache entry is locked for a request.

    Parameters
    ----------
    key : str
        The cache key to check, with the "request_locker::" prefix.
    timeout : int
        The maximum time to wait for the lock in seconds, by default 30.

    Returns
    -------
    bool
        True if the cache entry is locked and the lock is still valid, False otherwise.
    """
    entry = _cache.get(key)
    return isinstance(entry, PendingRequest) and (int(entry.elapsed_time.total_seconds()) < timeout)


def _entry_is_outdated(entry: PendingRequest, timeout: int) -> bool:
    return int(entry.elapsed_time.total_seconds()) >= timeout


def _try_acquire_lock(key: str) -> Optional[PendingRequest]:
    with _cache.lock(f"global_lock::{key}"):
        if key not in _cache:
            _cache[key] = PendingRequest()
    return _cache.get(key)


@contextmanager
def request_locker(key: str, timeout: int = 30):
    """Context manager to lock a cache entry for a request.

    This ensures that only one process can modify the cache entry for the given key at a time.
    If another process is already handling the request, this will wait until it is done.

    Parameters
    ----------
    key : str
        The cache key to lock.
    timeout : int
        The maximum time to wait for the lock in seconds, by default 30.

    Yields
    ------
    None
    """
    key = "request_locker::" + key
    lock = _try_acquire_lock(key)
    if isinstance(lock, PendingRequest):
        if not lock.is_from_current_thread:
            while not lock.has_timed_out(timeout):
                sleep(0.01)
    else:
        raise TypeError("Invalid lock type")
    try:
        yield lock
    finally:
        with _cache.transact():
            entry: Optional[PendingRequest] = _cache.get(key)
            if entry is not None and entry.is_from_current_thread:
                _cache.drop(key)
            elif entry is not None and _entry_is_outdated(entry, timeout):
                # help clean up stale locks even if not from this thread
                _cache.drop(key)
