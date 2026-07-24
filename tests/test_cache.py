import operator
import os
import shutil
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from unittest import mock
import dateutil.parser as dt_parser
import numpy as np
import packaging.version as Version
from ddt import data, ddt, unpack

import speasy.core.cache.cache as cache_mod
from speasy.core import epoch_to_datetime64
from speasy.core.cache import Cache, Cacheable, UnversionedProviderCache, drop_matching_entries, CacheCall
from speasy.core.cache.version import str_to_version, version_to_str
from speasy.products.variable import (DataContainer, SpeasyVariable,
                                      VariableTimeAxis)

start_date = datetime(2016, 6, 1, 12, tzinfo=timezone.utc)

dirpath = tempfile.mkdtemp()
cache = Cache(dirpath)


def data_generator(start_time, stop_time):
    index = np.array(
        [(start_time + timedelta(minutes=delta)).timestamp() for delta in
         range(int((stop_time - start_time).seconds / 60))])
    data = index / 3600.
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
        values=DataContainer(values=data))


@ddt
class _CacheTest(unittest.TestCase):
    def setUp(self):
        self._make_data_cntr = 0
        self._make_unversioned_data_cntr = 0
        self._version = 0

    def version(self, product):
        return self._version

    @Cacheable(prefix="", cache_instance=cache, version=version, leak_cache=True)
    def _make_data(self, product, start_time, stop_time):
        self._make_data_cntr += 1
        return data_generator(start_time, stop_time)

    @UnversionedProviderCache(prefix="", cache_instance=cache, leak_cache=True,
                              cache_retention=timedelta(microseconds=5e5))
    def _make_unversioned_data(self, product, start_time, stop_time, if_newer_than=None):
        if if_newer_than is None or (if_newer_than + timedelta(seconds=1)) < datetime.now(tz=timezone.utc):
            self._make_unversioned_data_cntr += 1
            return data_generator(start_time, stop_time)
        return None

    # Separate from _make_unversioned_data on purpose: that one needs a
    # sub-second retention so test_get_outdated_from_unversioned_cache's
    # time.sleep(3.) can trip real staleness without waiting the production
    # 14-day default. Sharing that thin margin with a rapid, non-sleeping
    # loop (below) left no headroom for a slow CI iteration to occur without
    # being mistaken for staleness -- this one gets its own generous margin
    # instead of being tuned to fit both use cases at once.
    @UnversionedProviderCache(prefix="", cache_instance=cache, leak_cache=True,
                              cache_retention=timedelta(minutes=5))
    def _make_stable_unversioned_data(self, product, start_time, stop_time, if_newer_than=None):
        self._make_unversioned_data_cntr += 1
        return data_generator(start_time, stop_time)

    def _get_and_check(self, start, stop, data_f):
        var = data_f(f"...{data_f}", start, stop)
        self.assertIsNotNone(var)
        self.assertEqual(var.time[0], np.datetime64(start, 'ns'))
        self.assertEqual(var.time[-1], np.datetime64(stop - timedelta(minutes=1), 'ns'))
        self.assertEqual(len(var), (stop - start).seconds / 60)

    def test_get_data_unversioned_prefer_cache(self):
        self._make_unversioned_data_cntr = 0
        var = self._make_unversioned_data("test_get_data_unversioned_prefer_cache", start_date,
                                          start_date + timedelta(minutes=10))
        self.assertIsNotNone(var)
        self.assertEqual(self._make_unversioned_data_cntr, 1)
        time.sleep(1)
        var = self._make_unversioned_data("test_get_data_unversioned_prefer_cache", start_date,
                                          start_date + timedelta(minutes=10))
        self.assertIsNotNone(var)
        self.assertEqual(self._make_unversioned_data_cntr, 2)
        var = self._make_unversioned_data("test_get_data_unversioned_prefer_cache", start_date,
                                          start_date + timedelta(minutes=10), prefer_cache=True)
        self.assertIsNotNone(var)
        self.assertEqual(self._make_unversioned_data_cntr, 2)

    def test_get_data_prefer_cache(self):
        self._make_data_cntr = 0
        self._version = "1.0.0"
        var = self._make_data("test_get_data_prefer_cache", start_date, start_date + timedelta(minutes=10))
        self.assertIsNotNone(var)
        self.assertEqual(self._make_data_cntr, 1)
        self._version = "1.0.1"
        var = self._make_data("test_get_data_prefer_cache", start_date, start_date + timedelta(minutes=10))
        self.assertIsNotNone(var)
        self.assertEqual(self._make_data_cntr, 2)
        self._version = "1.0.2"
        var = self._make_data("test_get_data_prefer_cache", start_date, start_date + timedelta(minutes=10),
                              prefer_cache=True)
        self.assertIsNotNone(var)
        self.assertEqual(self._make_data_cntr, 2)

    @data(
        (start_date, start_date + timedelta(minutes=10), "Less than one hour"),
        (start_date, start_date + timedelta(minutes=70), "More than one hour"),
        (start_date, start_date + timedelta(hours=13), "Over midnight")
    )
    @unpack
    def test_get_data(self, tstart, tend, name):
        self._get_and_check(tstart, tend, self._make_data)
        self._get_and_check(tstart, tend, self._make_unversioned_data)

    def test_get_data_more_than_once(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        for _ in range(10):
            var = self._make_data("test_get_data_more_than_once", tstart,
                                  tend)
            self.assertEqual(self._make_data_cntr, 1)

    def test_get_newer_version_data(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        for i in range(10):
            self._version = f"{i}"
            var = self._make_data("test_get_newer_version_data", tstart, tend)
            self.assertEqual(self._make_data_cntr, i + 1)

    def test_get_same_version_data(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        self._version = "1.1.1"
        for i in range(10):
            var = self._make_data("test_get_same_version_data", tstart, tend)
            self.assertEqual(self._make_data_cntr, 1)

    def test_get_cached_from_unversioned_cache(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_unversioned_data_cntr, 0)
        for i in range(10):
            var = self._make_stable_unversioned_data("test_get_cached_from_unversioned_cache", tstart, tend)
            self.assertEqual(self._make_unversioned_data_cntr, 1)

    def test_get_cached_from_unversioned_cache_survives_a_slow_iteration(self):
        # Regression test: a single slow loop iteration (a loaded CI runner
        # taking over a second to complete one round-trip) must not be
        # mistaken for real staleness. This drives a virtual clock instead
        # of relying on a real slow machine, so the bug reproduces on demand.
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        virtual_now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return virtual_now[0]

        with mock.patch.object(cache_mod, "datetime", FakeDateTime), \
             mock.patch.object(sys.modules[__name__], "datetime", FakeDateTime):
            for i in range(10):
                if i == 4:
                    virtual_now[0] += timedelta(seconds=2)
                self._make_stable_unversioned_data(
                    "test_get_cached_from_unversioned_cache_survives_a_slow_iteration", tstart, tend)
                self.assertEqual(self._make_unversioned_data_cntr, 1)

    def test_get_outdated_from_unversioned_cache(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_unversioned_data_cntr, 0)
        var = self._make_unversioned_data("test_get_outdated_from_unversioned_cache", tstart, tend)
        time.sleep(3.)
        var = self._make_unversioned_data("test_get_outdated_from_unversioned_cache", tstart, tend)
        self.assertEqual(self._make_unversioned_data_cntr, 2)

    def test_list_keys(self):
        keys = self._make_data.cache.keys()
        types = [type(key) for key in keys]
        self.assertGreater(len(keys), 0)
        self.assertListEqual(types, [str] * len(types))

    def test_global_keys(self, cache=cache):
        self.assertIsNone(cache.get("Not In Cache"))
        cache.set("In Cache", True)
        self.assertTrue(cache.get("In Cache"))

    def tearDown(self):
        pass


@ddt
class CacheRequestsDeduplication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._executor = ThreadPoolExecutor(max_workers=5)
        drop_matching_entries(r".*test_deduplication.*")

    @classmethod
    def tearDownClass(cls):
        cls._executor.shutdown()
        drop_matching_entries(r".*test_deduplication.*")

    def setUp(self):
        self._make_data_cntr = 0
        self._version = 0

    def version(self, product):
        return self._version

    @Cacheable(prefix="", version=version)
    def _make_data(self, product, start_time, stop_time):
        self._make_data_cntr += 1
        time.sleep(.001)
        return data_generator(start_time, stop_time)

    @data(*list(range(100)))
    def test_deduplication(self, step):
        # Each step uses its own product so cache entries never collide across
        # steps — lets the whole class share one cache and one thread pool
        # instead of paying a full cache scan + 5 fresh OS threads per step.
        product = f"test_deduplication_product_{step}"
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        futures = [self._executor.submit(self._make_data, product, tstart, tend) for _ in range(5)]
        wait(futures)
        self.assertLessEqual(self._make_data_cntr, 1)


class RequestLockerWakeup(unittest.TestCase):
    """Regression test: a peer waiting on a request_locker must wake up
    promptly once the producer drops the lock — not wait the full timeout.

    The previous implementation only checked a snapshot's elapsed time and
    ignored the cache state, so peers always slept for the full ``timeout``
    seconds even if the producer finished after milliseconds.
    """

    def test_peer_wakes_up_when_producer_finishes(self):
        from threading import Thread, Event
        from speasy.core.cache._request_locker import request_locker

        key = "test_request_locker_wakeup_prompt"
        producer_done = Event()
        peer_woken_at = []

        def producer():
            with request_locker(key, timeout=30):
                time.sleep(0.05)
            producer_done.set()

        def peer():
            time.sleep(0.01)
            t0 = time.monotonic()
            with request_locker(key, timeout=30):
                pass
            peer_woken_at.append(time.monotonic() - t0)

        t1 = Thread(target=producer)
        t2 = Thread(target=peer)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertTrue(producer_done.is_set())
        self.assertEqual(len(peer_woken_at), 1)
        self.assertLess(peer_woken_at[0], 1.0,
                        f"Peer waited {peer_woken_at[0]:.2f}s — should wake "
                        f"promptly after producer drops the lock")


class MPDataProvider:

    def version(self, product):
        return 0

    @staticmethod
    def increase_count(product) -> int:
        from speasy.core.cache import _cache
        return _cache.incr(f"CacheRequestsDeduplicationMultiProcess::{product}::counter", 1, default=0)

    @staticmethod
    def count(product):
        from speasy.core.cache import _cache
        return _cache.get(f"CacheRequestsDeduplicationMultiProcess::{product}::counter", 0)

    @staticmethod
    def reset_count(product):
        from speasy.core.cache import _cache
        _cache.drop(f"CacheRequestsDeduplicationMultiProcess::{product}::counter")

    @Cacheable(prefix="", version=version, deduplication_timeout=10)
    def make_data(self, product, start_time, stop_time):
        from threading import get_native_id
        print(f"Entering critical section for {product} {start_time} {stop_time} {get_native_id()}")
        r = self.increase_count(product)
        if r > 1:
            print(
                f"Warning, multiple process are in the critical section for {product} {start_time} {stop_time}, r= {r}")
        time.sleep(.001)
        return data_generator(start_time, stop_time)


def multi_process_make_data(product, start_time, stop_time):
    provider = MPDataProvider()
    return provider.make_data(product, start_time, stop_time)


@ddt
class CacheRequestsDeduplicationMultiProcess(unittest.TestCase):

    # A persistent Pool of 4 workers is reused across all 100 steps rather
    # than spawning a fresh Process() per step. This previously corrupted the
    # shared cache and hung a CI worker on pysciqlop-cache<0.1.4 (fork-safety
    # was only validated for a one-shot "fork, touch cache once, exit"
    # pattern); fixed upstream in pysciqlop-cache 0.1.4 (bounded retry for the
    # reused-pool TOCTOU race — see SciQLop/Sciqlop-cache
    # docs/known-issues/pool-reuse-fork-safety-gap.md).
    #
    # Per-step (not per-class) drop_matching_entries() is also intentional
    # here, unlike the thread-based dedup classes above.
    #
    # The pool's 4 workers each do a fresh `import speasy` once, at pool
    # creation. request_dispatch.py runs init_providers() at import time
    # unless SPEASY_SKIP_INIT_PROVIDERS is set, which does a live network
    # liveness check for every non-disabled provider - cheap here (4 imports
    # total) but was a 2+ hour Windows CI stall back when this test spawned a
    # fresh process (and fresh import) per step instead of reusing a pool.
    # Skip provider init for just this class - not the whole file - so it
    # doesn't leak into tests/test_zzz_disable_ws.py, which relies on a fresh
    # `import speasy` re-running init_providers() with different
    # SPEASY_CORE_DISABLED_PROVIDERS values.
    #
    # Explicitly force the 'spawn' start method (not the platform/version
    # default). Python 3.14 defaults Linux multiprocessing to 'forkserver',
    # which lazily starts a persistent server process on the *first* ever
    # Process()/Pool() in the whole test run and snapshots os.environ at that
    # moment - if anything (e.g. coverage instrumentation) starts it before
    # this class's setUpClass runs, every later child keeps seeing the
    # stale (pre-fix) environment no matter how much later os.environ is
    # mutated, since the server never re-reads it. Confirmed empirically:
    # a child spawned via the ambient forkserver context after setting the
    # env var still saw None, while the same spawn via an explicit
    # get_context('spawn') context saw the fix correctly - 'spawn' has no
    # persistent server, so it always re-inherits the current os.environ.
    @classmethod
    def setUpClass(cls):
        cls._prev_skip_init_providers = os.environ.get('SPEASY_SKIP_INIT_PROVIDERS')
        os.environ['SPEASY_SKIP_INIT_PROVIDERS'] = '1'
        from multiprocessing import get_context
        cls._pool = get_context('spawn').Pool(processes=4)

    @classmethod
    def tearDownClass(cls):
        cls._pool.close()
        cls._pool.join()
        if cls._prev_skip_init_providers is None:
            os.environ.pop('SPEASY_SKIP_INIT_PROVIDERS', None)
        else:
            os.environ['SPEASY_SKIP_INIT_PROVIDERS'] = cls._prev_skip_init_providers

    def setUp(self):
        drop_matching_entries(r".*CacheRequestsDeduplicationMultiProcess.*")

    def tearDown(self):
        drop_matching_entries(r".*CacheRequestsDeduplicationMultiProcess.*")

    @data(*list(range(100)))
    def test_deduplication(self, step):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        product = f"CacheRequestsDeduplicationMultiProcess::{step}"
        provider = MPDataProvider()
        provider.reset_count(product)
        self.assertEqual(provider.count(product), 0)
        results = [self._pool.apply_async(multi_process_make_data, (product, tstart, tend)) for _ in range(4)]
        for r in results:
            r.get()
        self.assertLessEqual(provider.count(product), 1)


@ddt
class _CacheVersionTest(unittest.TestCase):

    @data(
        ("1.1.1", "1.1.1", operator.eq),
        ("1.1.1", "1.1.2", operator.lt),
        ("1.1.1", "1.1.0", operator.gt),
        ("1", "1.0.0", operator.eq),
        ("1.1", "1.1.2", operator.lt),
        ("1.1.1", "1.1", operator.gt),
        ("1.1", "1.1", operator.eq),
        ("1.1", "1.2", operator.lt),
        ("1.1", "1.0", operator.gt),
        ("1", "1", operator.eq),
        ("1", "2", operator.lt),
        ("1", "0", operator.gt),
        ("2019-09-01T20:17:57Z", "2019-09-01T20:17:57Z", operator.eq),
        ("2019-09-01T20:17:57Z", "2019-09-01T21:17:57Z", operator.lt),
        ("2019-09-01T22:17:57Z", "2019-09-01T20:17:57Z", operator.gt)
    )
    @unpack
    def test_compare_version(self, lhs, rhs, op):
        self.assertTrue(op(str_to_version(lhs), str_to_version(rhs)))

    @data(
        ('1.2.3', Version.parse),
        ("2019-09-01T20:17:57Z", dt_parser.parse),
        ('-', lambda x: None)
    )
    @unpack
    def test_conversion(self, version_str, op):
        self.assertEqual(op(version_to_str(str_to_version(version_str))), op(version_str))


@CacheCall(cache_retention=timedelta(minutes=10), is_pure=True, cache_instance=cache, leak_cache=True)
def cache_test_function(key):
    return f"value_for_{key}"


class TestFunctionCache(unittest.TestCase):
    def test_can_clear_entries(self):
        cache = cache_test_function.cache
        cache["at least one key"] = True
        initial_keys_count = len(cache.keys())
        self.assertGreater(len(cache.keys()), 0)
        for i in range(10):
            cache_test_function(f"key_{i}")
        self.assertEqual(len(cache.keys()), initial_keys_count + 10)
        cache_test_function.drop_entries()
        self.assertEqual(len(cache.keys()), initial_keys_count)


class CacheResilientToUnreadableEntries(unittest.TestCase):
    """A cache entry written by an incompatible library version (e.g. numpy's on-disk
    pickle format changed between major versions) can fail to deserialize -- this must
    be treated as a cache miss, not crash the caller. Real-world trigger: a cache
    populated under one numpy major version, then read back under another."""

    def test_get_returns_default_when_backend_raises_on_deserialization(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        c = Cache(tmp)
        with mock.patch.object(c._data, "get", side_effect=ModuleNotFoundError("No module named 'numpy._core'")):
            with self.assertLogs("speasy.core.cache.cache", level="WARNING"):
                result = c.get("some_key", "fallback_default")
        self.assertEqual(result, "fallback_default")

    def test_get_or_lock_cache_entry_recovers_from_an_unreadable_pre_existing_entry(self):
        """get_or_lock_cache_entry's contract is Union[CacheItem, PendingRequest] -- if a
        pre-existing entry safety-netted to something else (e.g. None, once Cache.get()
        catches a deserialization error), it must drop and retry rather than handing back
        a value that crashes one line later in is_up_to_date()'s attribute access."""
        from speasy.core.cache._providers_caches import _Cacheable
        from speasy.core.cache._request_locker import PendingRequest

        class _FakeUnreadableThenHealthyCache:
            def __init__(self):
                self._store = {"stale_key": "not_a_cacheitem_or_pendingrequest"}

            def add(self, key, value, expire=None, tag=None):
                if key in self._store:
                    return False
                self._store[key] = value
                return True

            def get(self, key, default=None):
                return self._store.get(key, default)

            def drop(self, key):
                self._store.pop(key, None)

            def __contains__(self, key):
                return key in self._store

        cacheable = _Cacheable(prefix="p", cache_instance=_FakeUnreadableThenHealthyCache(),
                               entry_name=lambda *a, **k: "stale_key")
        entry = cacheable.get_or_lock_cache_entry(start_date, "product")
        self.assertIsInstance(entry, PendingRequest)


class TestNoopCacheBackend(unittest.TestCase):
    """The fallback backend used when pysciqlop_cache is unavailable (e.g. WASM)
    must never store anything and always report a miss."""

    def test_store_always_misses_and_saves_nothing(self):
        from speasy.core.cache import _noop_cache
        store = _noop_cache.Cache(cache_path="/unused", max_size=0)
        store.set("k", "v")
        store["k"] = "v"
        self.assertIsNone(store.get("k"))
        self.assertEqual(store.get("k", "default"), "default")
        self.assertEqual(len(store), 0)
        self.assertEqual(list(store), [])
        self.assertNotIn("k", store)
        self.assertTrue(store.add("k", "v"))  # nothing stored -> add succeeds
        self.assertIsNone(store.get("k"))
        with self.assertRaises(KeyError):
            store["k"]

    def test_store_mutations_are_inert(self):
        from speasy.core.cache import _noop_cache
        store = _noop_cache.Cache(cache_path="/unused", max_size=0)
        self.assertEqual(store.incr("counter", 2, default=5), 7)
        self.assertFalse(store.delete("k"))
        self.assertIsNone(store.pop("k"))
        self.assertEqual(store.pop("k", "d"), "d")
        self.assertEqual(store.evict_tag("t"), 0)
        self.assertEqual(store.expire(), 0)
        self.assertEqual(store.volume(), 0)
        self.assertEqual(store.stats(), {"hits": 0, "misses": 0})
        store.clear()
        store.reset_stats()
        with store.transact("shard"):
            pass

    def test_index_and_lock(self):
        from speasy.core.cache import _noop_cache
        index = _noop_cache.Index(path="/unused")
        index["mod/key"] = 1
        self.assertEqual(index.get("mod/key", "d"), "d")
        self.assertNotIn("mod/key", index)
        self.assertIsNone(index.pop("mod/key"))
        lock = _noop_cache.Lock(_noop_cache.Cache(), "k")
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.release())

    def test_speasy_cache_wrapper_works_on_noop_backend(self):
        import tempfile
        from unittest import mock
        import speasy.core.cache.cache as cache_mod
        from speasy.core.cache import _noop_cache
        with mock.patch.object(cache_mod, "sc", _noop_cache):
            cache = cache_mod.Cache(cache_path=tempfile.mkdtemp())
            cache.set("k", "v")
            self.assertIsNone(cache.get("k"))
            self.assertEqual(cache.stats(), {"hit": 0, "misses": 0})


_cache_call_dedup_cntr = {"n": 0}


@CacheCall(cache_retention=timedelta(minutes=10), is_pure=True, cache_instance=cache, leak_cache=True,
           deduplication_timeout=5)
def _cache_call_dedup_fn(key):
    _cache_call_dedup_cntr["n"] += 1
    time.sleep(.001)
    return f"value_for_{key}"


@ddt
class CacheCallRequestsDeduplication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._executor = ThreadPoolExecutor(max_workers=5)
        _cache_call_dedup_fn.drop_entries()

    @classmethod
    def tearDownClass(cls):
        cls._executor.shutdown()
        _cache_call_dedup_fn.drop_entries()

    def setUp(self):
        _cache_call_dedup_cntr["n"] = 0

    @data(*list(range(50)))
    def test_deduplication(self, step):
        futures = [self._executor.submit(_cache_call_dedup_fn, f"key_{step}") for _ in range(5)]
        wait(futures)
        self.assertLessEqual(_cache_call_dedup_cntr["n"], 1)

    def test_loser_does_not_impersonate_a_finished_owner(self):
        """Regression test for two related bugs, both needed to fully close
        the race:

        1. A TOCTOU bug in _try_acquire_lock: if the real owner finishes and
           drops the request_locker key between a loser's failed add() and
           that loser's fallback get(), Cache.get(key, default) used to
           return the loser's own default PendingRequest -- indistinguishable
           from real ownership (same thread, same object) even though nobody
           actually granted it the lock.
        2. Even once (1) is fixed so a retried add() legitimately re-acquires
           the (by-then-free) key, CacheCall.__call__ never re-checked the
           cache before recomputing when it won the lock -- so a genuinely
           late, legitimate second acquisition still redundantly re-ran the
           wrapped function after a previous owner already cached the value.

        Uses explicit events (not sleep-guessed timing) so the interleaving
        is deterministic instead of relying on scheduling luck.
        """
        from unittest import mock
        from threading import Thread, Event
        import speasy.core.cache._request_locker as rl

        owner_holds_lock = Event()
        owner_may_release = Event()
        owner_released = Event()
        run_count = {"n": 0}

        @CacheCall(cache_retention=timedelta(minutes=10), is_pure=True, cache_instance=_cache_call_dedup_fn.cache,
                   deduplication_timeout=5)
        def racy_fn(key):
            run_count["n"] += 1
            owner_holds_lock.set()
            owner_may_release.wait(timeout=2)
            return f"value_for_{key}"

        key = f"impersonation_race_{id(self)}"
        real_add = rl._cache.add

        def slow_add(*args, **kwargs):
            result = real_add(*args, **kwargs)
            if not result:
                # Lost the initial race (real contention: owner already holds
                # the key). Stall here -- exactly between add() failing and
                # the caller's fallback get() -- until the owner has actually
                # released, forcing the TOCTOU window open every time.
                owner_may_release.set()
                owner_released.wait(timeout=2)
            return result

        def owner():
            racy_fn(key)
            owner_released.set()

        def loser():
            owner_holds_lock.wait(timeout=2)  # ensure real contention first
            racy_fn(key)

        with mock.patch.object(type(rl._cache), "add", side_effect=slow_add):
            t_owner = Thread(target=owner)
            t_loser = Thread(target=loser)
            t_owner.start()
            t_loser.start()
            t_owner.join(timeout=5)
            t_loser.join(timeout=5)

        self.assertLessEqual(run_count["n"], 1)


if __name__ == '__main__':
    unittest.main()

try:
    del cache
    shutil.rmtree(dirpath)
except PermissionError:
    print(f"Can't rm temporary cache folder {dirpath}")
