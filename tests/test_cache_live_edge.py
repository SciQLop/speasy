import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import numpy as np

import speasy.core.cache._providers_caches as providers_caches
from speasy.core import epoch_to_datetime64
from speasy.core.cache import Cache, Cacheable
from speasy.core.datetime_range import DateTimeRange
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis

_cache = Cache(tempfile.mkdtemp())
_COVERAGE_START = datetime(2026, 8, 1, tzinfo=timezone.utc)
_FIRST_COVERAGE_END = datetime(2026, 8, 27, tzinfo=timezone.utc)


def _minutely(start_time, stop_time):
    index = np.arange(start_time.timestamp(), stop_time.timestamp(), 60.)
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
                          values=DataContainer(values=index / 3600.))


class _GrowingDataset:
    """An AMDA-like dataset that gains new data without its version changing, as AMDA's
    lastModificationDate does when it only appends data."""

    def __init__(self, coverage_end=_FIRST_COVERAGE_END):
        self.coverage_end = coverage_end
        self.calls = 0

    def parameter_range(self, product):
        return DateTimeRange(_COVERAGE_START, self.coverage_end)

    @Cacheable(prefix="live_edge", cache_instance=_cache, version=lambda self, product: "2025-03-24T05:12:04Z",
               fragment_hours=lambda x: 12)
    def get_data(self, product, start_time, stop_time):
        self.calls += 1
        return _minutely(start_time, min(stop_time, self.coverage_end))


class _NoCoverageInfo:
    def __init__(self):
        self.calls = 0

    @Cacheable(prefix="live_edge_no_range", cache_instance=_cache, version=lambda self, product: 1,
               fragment_hours=lambda x: 12)
    def get_data(self, product, start_time, stop_time):
        self.calls += 1
        return _minutely(start_time, stop_time)


class LiveEdgeFragments(unittest.TestCase):
    def setUp(self):
        _cache.drop_matching_entries(".*")

    def test_data_added_after_the_coverage_end_is_fetched_later(self):
        dataset = _GrowingDataset()
        start, stop = _FIRST_COVERAGE_END - timedelta(days=1), _FIRST_COVERAGE_END + timedelta(days=1)
        with mock.patch.object(providers_caches, "PROVISIONAL_FRAGMENT_LIFETIME", timedelta(0)):
            self.assertLess(dataset.get_data("ace", start, stop).time[-1], np.datetime64("2026-08-27"))

        dataset.coverage_end = stop
        refreshed = dataset.get_data("ace", start, stop)

        self.assertEqual(refreshed.time[-1], np.datetime64("2026-08-27T23:59"))

    def test_fragments_inside_the_coverage_stay_cached(self):
        dataset = _GrowingDataset()
        start, stop = _FIRST_COVERAGE_END - timedelta(days=3), _FIRST_COVERAGE_END - timedelta(days=2)
        with mock.patch.object(providers_caches, "PROVISIONAL_FRAGMENT_LIFETIME", timedelta(0)):
            dataset.get_data("ace", start, stop)
        dataset.get_data("ace", start, stop)
        self.assertEqual(dataset.calls, 1)

    def test_live_edge_fragments_are_reused_until_they_expire(self):
        dataset = _GrowingDataset()
        start, stop = _FIRST_COVERAGE_END - timedelta(days=1), _FIRST_COVERAGE_END + timedelta(days=1)
        dataset.get_data("ace", start, stop)
        dataset.get_data("ace", start, stop)
        self.assertEqual(dataset.calls, 1)

    def test_provider_without_coverage_info_caches_as_before(self):
        provider = _NoCoverageInfo()
        start = _FIRST_COVERAGE_END
        with mock.patch.object(providers_caches, "PROVISIONAL_FRAGMENT_LIFETIME", timedelta(0)):
            provider.get_data("p", start, start + timedelta(days=1))
            provider.get_data("p", start, start + timedelta(days=1))
        self.assertEqual(provider.calls, 1)


if __name__ == "__main__":
    unittest.main()
