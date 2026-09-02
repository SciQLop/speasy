"""TDD tests for the self-healing cache epoch mechanism.

Background: speasy could cache empty fragments (0-row, or all-NaN padding
rows) as permanent cache entries. Those entries never expire and keep
serving empty data forever, even after upstream backfills the real data.

The fix stamps every CacheItem with a ``cache_epoch`` (the writer's speasy
version, packed as an int) at write time. On read, an entry written before a
version that fixed a known-broken-entry class is checked against that
class's predicate; a match is treated as a cache miss so the caller refetches
and overwrites it with fresh data stamped with the current epoch.
"""
import pickle
import tempfile
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import speasy.core.cache.cache as cache_mod
from speasy.core import epoch_to_datetime64
from speasy.core.cache.cache import Cache, CacheItem
from speasy.core.cache._providers_caches import (
    _Cacheable,
    _is_empty,
    _should_discard,
    DISCARD_RULES,
    UnversionedProviderCache,
)
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis, to_dictionary


# ---------------------------------------------------------------------------
# 1. _version_to_epoch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("version_str, expected", [
    ("1.8.1", 1_008_001),
    ("1.8.1.dev3+g1a2b3c4", 1_008_001),
    ("1.9.0.dev5+gabc123.dirty", 1_009_000),
    ("0.0.0.dev0", 0),
    ("2.0.0", 2_000_000),
])
def test_version_to_epoch(version_str, expected):
    assert cache_mod._version_to_epoch(version_str) == expected


# ---------------------------------------------------------------------------
# 2. CacheItem backward / forward compatibility
# ---------------------------------------------------------------------------

def test_new_cache_item_gets_current_epoch():
    item = CacheItem(data={"x": 1}, version=1)
    assert item.cache_epoch == cache_mod._CURRENT_CACHE_EPOCH


def test_cache_item_setstate_defaults_missing_epoch_to_zero():
    legacy_state = {"data": {"x": 1}, "version": 1, "lifetime": None,
                    "created": datetime.now(tz=timezone.utc)}
    assert "cache_epoch" not in legacy_state

    item = CacheItem.__new__(CacheItem)
    item.__setstate__(legacy_state)
    assert item.cache_epoch == 0


def test_cache_item_unpickle_legacy_pickle_defaults_epoch_to_zero():
    # pickle.loads here round-trips a CacheItem this same test just created
    # in-process (not untrusted external input) to exercise __setstate__.
    item = CacheItem(data={"x": 1}, version=1)
    del item.cache_epoch  # simulate a pickle produced before cache_epoch existed
    restored = pickle.loads(pickle.dumps(item))
    assert restored.cache_epoch == 0


def test_cache_item_setstate_ignores_unknown_future_keys():
    # Forward-compat sketch: an *older* Speasy's __setstate__ (pre cache_epoch)
    # reading a state dict that DOES have cache_epoch must not crash.
    def legacy_setstate(self, state):
        self.data = state["data"]
        self.version = state["version"]
        self.lifetime = state.get("lifetime", None)
        self.created = state.get("created", datetime.now(tz=timezone.utc))

    state_with_epoch = {
        "data": {"x": 1}, "version": 1, "lifetime": None,
        "created": datetime.now(tz=timezone.utc), "cache_epoch": 1_008_001,
    }
    item = CacheItem.__new__(CacheItem)
    legacy_setstate(item, state_with_epoch)
    assert item.data == {"x": 1}
    assert not hasattr(item, "cache_epoch")


# ---------------------------------------------------------------------------
# 3. _is_empty
# ---------------------------------------------------------------------------

def _variable_dict(n_rows, shape_extra=(), fill=1.0, dtype=np.float64):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    index = np.array([(start + timedelta(minutes=i)).timestamp() for i in range(n_rows)])
    shape = (n_rows,) + shape_extra
    values = np.full(shape, fill, dtype=dtype)
    var = SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
                         values=DataContainer(values=values))
    return to_dictionary(var)


def test_is_empty_zero_rows():
    assert _is_empty(_variable_dict(0)) is True


def test_is_empty_all_nan_short_fragment():
    assert _is_empty(_variable_dict(2, shape_extra=(3,), fill=np.nan)) is True


def test_is_empty_finite_short_fragment_is_not_empty():
    assert _is_empty(_variable_dict(12, shape_extra=(3,), fill=1.0)) is False


def test_is_empty_large_finite_fragment_is_not_empty():
    assert _is_empty(_variable_dict(100, shape_extra=(3,), fill=1.0)) is False


def test_is_empty_int_dtype_is_never_empty():
    assert _is_empty(_variable_dict(2, dtype=np.int64)) is False


@pytest.mark.parametrize("malformed", [{}, {"result": 42}, "not-even-a-dict"])
def test_is_empty_malformed_payload_is_never_empty(malformed):
    assert _is_empty(malformed) is False


# ---------------------------------------------------------------------------
# 4. _should_discard
# ---------------------------------------------------------------------------

def _item_with_epoch(data, epoch):
    item = CacheItem(data=data, version=None)
    item.cache_epoch = epoch
    return item


def test_should_discard_empty_legacy_epoch():
    assert _should_discard(_item_with_epoch(_variable_dict(0), 0)) is True


def test_should_discard_empty_current_epoch_is_kept():
    # "Current" here means "the epoch a fresh write gets once this fix has
    # shipped" (i.e. >= the DISCARD_RULES gate), not literally whatever
    # version string this particular dev checkout happens to report --
    # editable-install metadata is frozen at install time and this repo may
    # not have cut the release tag the gate refers to yet.
    assert _should_discard(_item_with_epoch(_variable_dict(0), DISCARD_RULES[0][0])) is False


def test_should_discard_empty_written_by_1_8_0_is_discarded():
    assert _should_discard(_item_with_epoch(_variable_dict(0), 1_008_000)) is True


def test_should_discard_non_empty_legacy_epoch_is_kept():
    assert _should_discard(_item_with_epoch(_variable_dict(12, shape_extra=(3,)), 0)) is False


def test_discard_rules_gate_is_1_8_1():
    assert DISCARD_RULES[0][0] == 1_008_001


# ---------------------------------------------------------------------------
# 5. get_from_cache integration
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cache_instance():
    dirpath = tempfile.mkdtemp()
    return Cache(dirpath)


def _cacheable(cache_instance, prefix):
    return _Cacheable(prefix=prefix, cache_instance=cache_instance)


def test_legacy_empty_entry_not_returned_even_with_prefer_cache(cache_instance):
    c = _cacheable(cache_instance, "heal-legacy-empty")
    fragment = datetime(2020, 1, 1, tzinfo=timezone.utc)
    item = _item_with_epoch(_variable_dict(0), 0)
    c.set_cache_entry(fragment, "prod", item)

    assert c.get_from_cache(fragment, "prod", version=None, prefer_cache=False) is None
    assert c.get_from_cache(fragment, "prod", version=None, prefer_cache=True) is None


def test_current_empty_entry_is_returned(cache_instance):
    # Same rationale as test_should_discard_empty_current_epoch_is_kept: stamp
    # with the gate value itself, i.e. the smallest epoch that must NOT be
    # discarded, rather than this checkout's (possibly pre-release) reported
    # version.
    c = _cacheable(cache_instance, "heal-current-empty")
    fragment = datetime(2020, 1, 1, tzinfo=timezone.utc)
    item = _item_with_epoch(_variable_dict(0), DISCARD_RULES[0][0])
    c.set_cache_entry(fragment, "prod", item)

    result = c.get_from_cache(fragment, "prod", version=None, prefer_cache=True)
    assert result is not None
    assert len(result) == 0


def test_legacy_non_empty_entry_is_returned(cache_instance):
    c = _cacheable(cache_instance, "heal-legacy-nonempty")
    fragment = datetime(2020, 1, 1, tzinfo=timezone.utc)
    item = _item_with_epoch(_variable_dict(12, shape_extra=(3,)), 0)
    c.set_cache_entry(fragment, "prod", item)

    result = c.get_from_cache(fragment, "prod", version=None, prefer_cache=True)
    assert result is not None
    assert len(result) == 12


# ---------------------------------------------------------------------------
# 6. Convergence: a healed fragment is rewritten with the current epoch and
#    stops being discarded on the next read (no thrash).
# ---------------------------------------------------------------------------

def test_healed_fragment_converges_after_rewrite(cache_instance):
    c = _cacheable(cache_instance, "heal-converge")
    fragment = datetime(2020, 1, 1, tzinfo=timezone.utc)
    legacy_empty = _item_with_epoch(_variable_dict(0), 0)
    c.set_cache_entry(fragment, "prod", legacy_empty)

    assert c.get_from_cache(fragment, "prod", version=None, prefer_cache=True) is None

    fresh_var = SpeasyVariable.from_dictionary(_variable_dict(12, shape_extra=(3,)))
    c.add_to_cache(fresh_var, [fragment], "prod", fragment_duration=timedelta(hours=1),
                  version=None, lifetime=None)

    result = c.get_from_cache(fragment, "prod", version=None, prefer_cache=True)
    assert result is not None
    assert len(result) == 12


# ---------------------------------------------------------------------------
# 7. UnversionedProviderCache.split_fragments (CDA-style provider family) --
#    it has its own read path (not funneled through _Cacheable.get_from_cache
#    or get_or_lock_from_cache), so it needs its own _should_discard wiring.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def unversioned_provider():
    dirpath = tempfile.mkdtemp()
    cache = Cache(dirpath)
    return UnversionedProviderCache(prefix="heal-unversioned", cache_instance=cache,
                                    cache_retention=timedelta(days=14))


def _put_unversioned_entry(provider, fragment, product, data, epoch):
    item = CacheItem(data=data, version=provider.version, lifetime=provider.cache_retention)
    item.cache_epoch = epoch
    provider._cache.set_cache_entry(fragment, product, item)


def test_split_fragments_discards_legacy_empty_entry_even_with_prefer_cache(unversioned_provider):
    fragment = datetime(2020, 1, 1, tzinfo=timezone.utc)
    _put_unversioned_entry(unversioned_provider, fragment, "prod", _variable_dict(0), epoch=0)

    data_chunks, maybe_outdated, missing = unversioned_provider.split_fragments(
        [fragment], "prod", timedelta(hours=1), prefer_cache=True)

    assert data_chunks == []
    assert maybe_outdated == []
    assert missing == [[fragment]]


def test_split_fragments_keeps_legacy_non_empty_entry(unversioned_provider):
    fragment = datetime(2020, 1, 1, tzinfo=timezone.utc)
    _put_unversioned_entry(unversioned_provider, fragment, "prod2", _variable_dict(12, shape_extra=(3,)), epoch=0)

    data_chunks, maybe_outdated, missing = unversioned_provider.split_fragments(
        [fragment], "prod2", timedelta(hours=1), prefer_cache=True)

    assert len(data_chunks) == 1
    assert len(data_chunks[0]) == 12
    assert missing == []


def test_split_fragments_keeps_current_epoch_empty_entry(unversioned_provider):
    fragment = datetime(2020, 1, 1, tzinfo=timezone.utc)
    _put_unversioned_entry(unversioned_provider, fragment, "prod3", _variable_dict(0),
                           epoch=DISCARD_RULES[0][0])

    data_chunks, maybe_outdated, missing = unversioned_provider.split_fragments(
        [fragment], "prod3", timedelta(hours=1), prefer_cache=True)

    assert len(data_chunks) == 1
    assert len(data_chunks[0]) == 0
    assert missing == []


def test_is_empty_on_speasyvariable_object_does_not_raise():
    # Pre-"dict repr" entries stored a SpeasyVariable object directly; indexing
    # one raises ValueError. _is_empty must treat any non-dict payload as
    # "can't judge -> not empty", never crash the read path (regression).
    import numpy as np
    from speasy.products.variable import (DataContainer, SpeasyVariable,
                                          VariableTimeAxis)
    from speasy.core.cache._providers_caches import _is_empty, _should_discard
    from speasy.core.cache.cache import CacheItem
    var = SpeasyVariable(
        axes=[VariableTimeAxis(values=np.array(['2020-01-01T00:00:00'], dtype='datetime64[ns]'))],
        values=DataContainer(values=np.array([[1.0]], dtype='float64'), meta={}),
        columns=['a'])
    assert _is_empty(var) is False
    assert _is_empty("a plain string") is False
    assert _is_empty(12345) is False
    item = CacheItem(var, version="1")
    item.cache_epoch = 0
    assert _should_discard(item) is False   # must not raise
