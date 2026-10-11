"""UnversionedProviderCache must fetch a fragment once when concurrent callers ask for it (#371)."""
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np

from speasy.core import epoch_to_datetime64
from speasy.core.cache import Cache, UnversionedProviderCache
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis

cache = Cache(tempfile.mkdtemp())
start = datetime(2016, 6, 1, 12, tzinfo=timezone.utc)
stop = start + timedelta(minutes=30)
RETENTION = timedelta(milliseconds=300)


def make_variable(start_time, stop_time):
    index = np.arange(start_time.timestamp(), stop_time.timestamp(), 60.)
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
                          values=DataContainer(values=index / 3600.))


class FakeProvider:
    def __init__(self, answer="data", delay=0.2):
        self.answer = answer
        self.delay = delay
        self.calls = 0
        self._lock = threading.Lock()

    @UnversionedProviderCache(prefix="dedup", cache_instance=cache, cache_retention=RETENTION)
    def get_data(self, product, start_time, stop_time, if_newer_than=None):
        with self._lock:
            self.calls += 1
        time.sleep(self.delay)
        if self.answer == "error":
            raise ConnectionError("upstream down")
        if self.answer == "not modified" and if_newer_than is not None:
            return None
        if self.answer == "empty":
            return None
        return make_variable(start_time, stop_time)


def call_concurrently(provider, product, count=2, **kwargs):
    barrier = threading.Barrier(count)

    def fetch():
        barrier.wait()
        return provider.get_data(product, start, stop, **kwargs)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return [f.result(timeout=10) for f in [pool.submit(fetch) for _ in range(count)]]


class UnversionedCacheDeduplication(unittest.TestCase):
    def setUp(self):
        self.product = self.id()
        cache.drop_matching_entries(f".*{self.product}.*")

    def prime_then_expire(self, provider):
        provider.get_data(self.product, start, stop)
        time.sleep(RETENTION.total_seconds() * 1.5)
        provider.calls = 0

    def test_concurrent_requests_for_an_uncached_range_fetch_once(self):
        provider = FakeProvider()
        results = call_concurrently(provider, self.product, count=4)
        self.assertEqual(provider.calls, 1)
        for var in results:
            self.assertEqual(len(var), 30)

    def test_concurrent_revalidations_of_an_expired_range_fetch_once(self):
        provider = FakeProvider()
        self.prime_then_expire(provider)
        results = call_concurrently(provider, self.product, count=4)
        self.assertEqual(provider.calls, 1)
        for var in results:
            self.assertEqual(len(var), 30)

    def test_waiters_get_the_bumped_entry_when_upstream_says_not_modified(self):
        provider = FakeProvider()
        self.prime_then_expire(provider)
        provider.answer = "not modified"
        results = call_concurrently(provider, self.product, count=4)
        self.assertEqual(provider.calls, 1)
        for var in results:
            self.assertEqual(len(var), 30)

    def test_an_empty_answer_does_not_leave_the_range_locked(self):
        provider = FakeProvider(answer="empty", delay=0)
        self.assertIsNone(provider.get_data(self.product, start, stop))
        with ThreadPoolExecutor(max_workers=1) as other_thread:
            self.assertIsNone(other_thread.submit(provider.get_data, self.product, start, stop).result(timeout=5))

    def test_a_failed_fetch_does_not_leave_the_range_locked(self):
        provider = FakeProvider(answer="error", delay=0)
        with self.assertRaises(ConnectionError):
            provider.get_data(self.product, start, stop)
        provider.answer = "data"
        with ThreadPoolExecutor(max_workers=1) as other_thread:
            self.assertEqual(len(other_thread.submit(provider.get_data, self.product, start, stop).result(timeout=5)),
                             30)

    def test_a_failed_revalidation_keeps_the_stale_entry(self):
        provider = FakeProvider(delay=0)
        self.prime_then_expire(provider)
        provider.answer = "error"
        with self.assertRaises(ConnectionError):
            provider.get_data(self.product, start, stop)
        provider.calls = 0
        self.assertEqual(len(provider.get_data(self.product, start, stop, prefer_cache=True)), 30)
        self.assertEqual(provider.calls, 0)


if __name__ == '__main__':
    unittest.main()
