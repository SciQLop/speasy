from contextlib import contextmanager
from datetime import datetime, timezone
from time import sleep
from typing import Optional

from ._instance import _cache
from ..platform import is_running_on_wasm

if is_running_on_wasm():
    get_native_id = lambda: 0
else:
    from threading import get_native_id


PENDING_REQUEST_TAG = "pending_request"


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
    """Check if a cache entry is locked for a request."""
    entry = _cache.get(key)
    return isinstance(entry, PendingRequest) and (int(entry.elapsed_time.total_seconds()) < timeout)


def _try_acquire_lock(key: str, timeout: int) -> Optional[PendingRequest]:
    """Atomically claim ``key`` for the current thread, or return the existing
    pending request if another thread/process owns it.

    Uses ``Cache.add(expire=)`` so a crashed lock-holder is automatically
    cleaned up by the cache after ``timeout`` seconds — no manual reaping
    needed. The ``pending_request`` tag enables bulk eviction on startup.
    """
    new_request = PendingRequest()
    if _cache.add(key, new_request, expire=timeout, tag=PENDING_REQUEST_TAG):
        return new_request
    return _cache.get(key, new_request)


def evict_pending_requests():
    """Drop all pending-request markers — useful on proxy/server startup
    to avoid stale entries from a previous unclean shutdown.
    """
    _cache.evict_tag(PENDING_REQUEST_TAG)


@contextmanager
def request_locker(key: str, timeout: int = 30):
    """Context manager to lock a cache entry for a request.

    Ensures only one process modifies the cache entry for ``key`` at a time.
    If another process is already handling the request, this waits until that
    request finishes (the key disappears) or the lock times out.
    """
    key = "request_locker::" + key
    lock = _try_acquire_lock(key, timeout)
    if isinstance(lock, PendingRequest):
        if not lock.is_from_current_thread:
            while key in _cache and not lock.has_timed_out(timeout):
                sleep(0.01)
    else:
        raise TypeError(f"Invalid lock type for key {key}: {type(lock)}")
    try:
        yield lock
    finally:
        entry: Optional[PendingRequest] = _cache.get(key)
        if entry is not None and (entry.is_from_current_thread or entry.has_timed_out(timeout)):
            _cache.drop(key)
