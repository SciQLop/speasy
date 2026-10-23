import tempfile
import unittest
from datetime import datetime, timezone

import numpy as np

from speasy.core import epoch_to_datetime64
from speasy.core.cache import CACHE_ALLOWED_KWARGS, Cache, Cacheable, UnversionedProviderCache
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis

_cache = Cache(tempfile.mkdtemp())
_START = datetime(2026, 8, 1, tzinfo=timezone.utc)
_STOP = datetime(2026, 8, 2, tzinfo=timezone.utc)


def _minutely(start_time, stop_time, generation):
    index = np.arange(start_time.timestamp(), stop_time.timestamp(), 60.)
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
                          values=DataContainer(values=np.full(len(index), float(generation))))


class _Dataset:
    """Serves data tagged with how many times it was fetched, so a refetch is visible in the values."""

    def __init__(self):
        self.calls = []
        self.offline = False

    def _serve(self, start_time, stop_time, **kwargs):
        if self.offline:
            raise ConnectionError("offline")
        self.calls.append(kwargs)
        return _minutely(start_time, stop_time, len(self.calls))


class _VersionedDataset(_Dataset):
    @Cacheable(prefix="force_refresh", cache_instance=_cache, version=lambda self, product: 1,
               fragment_hours=lambda x: 12)
    def get_data(self, product, start_time, stop_time, disable_proxy=False):
        return self._serve(start_time, stop_time, disable_proxy=disable_proxy)


class _UnversionedDataset(_Dataset):
    @UnversionedProviderCache(prefix="force_refresh_unversioned", cache_instance=_cache, fragment_hours=lambda x: 12)
    def get_data(self, product, start_time, stop_time, if_newer_than=None, disable_proxy=False):
        return self._serve(start_time, stop_time, if_newer_than=if_newer_than, disable_proxy=disable_proxy)


class ForceRefresh:
    """Shared by both provider caches, see the subclasses below."""
    dataset_class = None

    def setUp(self):
        _cache.drop_matching_entries(".*")
        self.dataset = self.dataset_class()
        self.dataset.get_data("ace", _START, _STOP)

    def test_fetches_even_when_the_cache_is_fresh(self):
        refreshed = self.dataset.get_data("ace", _START, _STOP, force_refresh=True)
        self.assertEqual(len(self.dataset.calls), 2)
        self.assertTrue(np.all(refreshed.values == 2.))

    def test_writes_the_new_data_back_to_the_cache(self):
        self.dataset.get_data("ace", _START, _STOP, force_refresh=True)
        cached = self.dataset.get_data("ace", _START, _STOP)
        self.assertEqual(len(self.dataset.calls), 2)
        self.assertTrue(np.all(cached.values == 2.))

    def test_bypasses_the_proxy(self):
        self.dataset.get_data("ace", _START, _STOP, force_refresh=True)
        self.assertTrue(self.dataset.calls[-1]["disable_proxy"])

    def test_a_normal_request_keeps_using_the_proxy(self):
        self.assertFalse(self.dataset.calls[-1]["disable_proxy"])


class VersionedCacheForceRefresh(ForceRefresh, unittest.TestCase):
    dataset_class = _VersionedDataset


class UnversionedCacheForceRefresh(ForceRefresh, unittest.TestCase):
    dataset_class = _UnversionedDataset

    def test_does_not_ask_only_for_newer_data(self):
        # with if_newer_than the server may answer "not modified" and the old data would stay
        self.dataset.get_data("ace", _START, _STOP, force_refresh=True)
        self.assertIsNone(self.dataset.calls[-1]["if_newer_than"])

    def test_a_failed_refresh_keeps_the_cached_data(self):
        self.dataset.offline = True
        with self.assertRaises(ConnectionError):
            self.dataset.get_data("ace", _START, _STOP, force_refresh=True)
        cached = self.dataset.get_data("ace", _START, _STOP)
        self.assertTrue(np.all(cached.values == 1.))


class AllowedEverywhere(unittest.TestCase):
    def test_every_provider_accepts_force_refresh(self):
        self.assertIn("force_refresh", CACHE_ALLOWED_KWARGS)


if __name__ == '__main__':
    unittest.main()
