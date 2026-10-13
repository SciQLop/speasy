"""HAPI JSON → Speasy inventory tree, with lazily loaded server and dataset nodes (no network access here).

See https://github.com/hapi-server/data-specification/blob/master/hapi-3.3.0/HAPI-data-access-spec-3.3.0.md
"""
import logging
import re
import time
from datetime import timedelta
from threading import Lock
from typing import Callable, Dict, Iterable, List, Mapping, Optional

from speasy.core import fix_name
from speasy.core.codecs.bundled_codecs.hapi.isotime import day_of_year_to_calendar
from speasy.core.inventory.indexes import DatasetIndex, ParameterIndex, SpeasyIndex

log = logging.getLogger(__name__)

_NOT_DATASET_META = ('HAPI', 'status', 'parameters')
_LOADED = 'hapi_loaded'

_NUMBER = r'(\d+(?:\.\d+)?)'
_DURATION = re.compile(
    rf'^P(?:{_NUMBER}Y)?(?:{_NUMBER}M)?(?:{_NUMBER}W)?(?:{_NUMBER}D)?(?:T(?:{_NUMBER}H)?(?:{_NUMBER}M)?(?:{_NUMBER}S)?)?$')

FAILED_LOAD_BACKOFF = 60
"""Seconds during which implicit accesses (hasattr, dir, completion) don't retry a failed load: retrying an unreachable
server takes tens of seconds, holding the node's lock."""

_load_locks: Dict[tuple, Lock] = {}
_load_locks_guard = Lock()
_failed_loads: Dict[tuple, float] = {}


def normalized_time(hapi_time: str) -> str:
    """HAPI allows date-only and day-of-year times (``1970-01-01Z``, ``2015-032T00:00Z``), which Speasy can't parse."""
    t = day_of_year_to_calendar(hapi_time.strip().rstrip('Z'))
    return (t if 'T' in t else f"{t}T00:00") + 'Z'


def iso8601_duration(text: Optional[str]) -> Optional[timedelta]:
    """Years count 365 days and months 28, the shortest: a request split on this never exceeds the server's limit."""
    m = _DURATION.match(text) if isinstance(text, str) else None
    if m is None or not any(m.groups()):
        return None
    years, months, weeks, days, hours, minutes, seconds = (float(g or 0) for g in m.groups())
    return timedelta(days=365 * years + 28 * months + 7 * weeks + days, hours=hours, minutes=minutes, seconds=seconds)


class _LazyIndex:
    """Fills itself through ``loader`` (set by the HAPI provider) on first access to a missing name."""
    loader: Optional[Callable[[SpeasyIndex], None]] = None

    def _load(self, implicit: bool = False) -> None:
        if self.__dict__.get(_LOADED, False):
            return
        key = _node_key(self)
        with _lock_for(self):
            if self.__dict__.get(_LOADED, False) or type(self).loader is None:
                return
            if implicit and time.monotonic() - _failed_loads.get(key, -FAILED_LOAD_BACKOFF) < FAILED_LOAD_BACKOFF:
                return
            try:
                type(self).loader(self)
            except Exception:
                _failed_loads[key] = time.monotonic()
                raise
            _failed_loads.pop(key, None)

    def _try_load(self) -> None:
        # Swallowed: hasattr() and tree walkers must not crash on an unreachable server, a later access retries.
        try:
            self._load(implicit=True)
        except Exception as e:  # pylint: disable=broad-except
            log.warning(f"Could not load HAPI node {self.spz_uid()}: {e!r}")

    def __getattr__(self, name):
        if not name.startswith('_'):
            self._try_load()
            if name in self.__dict__:
                return self.__dict__[name]
        raise AttributeError(name)

    def __dir__(self):
        self._try_load()
        return super().__dir__()


class HapiServerIndex(_LazyIndex, SpeasyIndex):
    def __repr__(self):
        return f'<HapiServerIndex: {self.spz_name()}>'


class HapiDatasetIndex(_LazyIndex, DatasetIndex):
    def __repr__(self):
        return f'<HapiDatasetIndex: {self.spz_name()}>'

    def __iter__(self):
        self._try_load()
        return super().__iter__()

    def __contains__(self, item):
        self._try_load()
        return super().__contains__(item)


def _node_key(node: SpeasyIndex) -> tuple:
    return type(node).__name__, node.spz_provider(), node.spz_uid()


def _lock_for(node: SpeasyIndex) -> Lock:
    with _load_locks_guard:
        return _load_locks.setdefault(_node_key(node), Lock())


def load_into(node: SpeasyIndex, fill: Callable[[SpeasyIndex], None]) -> None:
    """Builds ``node``'s content on a copy, then swaps its ``__dict__`` at once: a reader iterating the old dict never
    sees it change size, and a failed ``fill`` leaves ``node`` untouched."""
    meta = {k: v for k, v in node.__dict__.items() if not k.startswith('__spz_')}
    staging = type(node)(name=node.spz_name(), provider=node.spz_provider(), uid=node.spz_uid(),
                         meta={**meta, _LOADED: True})
    fill(staging)
    node.__dict__ = staging.__dict__


def build_inventory(root: SpeasyIndex, server_meta: Mapping, catalog: Iterable[Mapping],
                    dataset_type: type = DatasetIndex) -> SpeasyIndex:
    """Fills ``root``, the node of one HAPI server, with one node per catalog entry.

    UIDs are ``<root uid>/<dataset id>[/<parameter name>]``, so ``root``'s uid must be the server key.

    ``catalog`` has the shape of ``/catalog?depth=all``: ``{"id", "title", "info"?}`` entries, where ``info`` is the
    ``/info`` response for that dataset. Entries without ``info`` become datasets holding only their title, to be
    filled later with :func:`fill_dataset` when ``dataset_type`` is lazy.
    """
    root.__dict__.update(server_meta)
    for entry in catalog:
        _add_dataset(root, entry, dataset_type)
    return root


def fill_dataset(dataset: DatasetIndex, info: Mapping) -> None:
    dataset.__dict__.update(_dataset_meta(info))
    for parameter in info.get('parameters', [])[1:]:
        _add_parameter(dataset, parameter)


def _add_dataset(root: SpeasyIndex, entry: Mapping, dataset_type: type) -> None:
    provider = root.spz_provider()
    *folders, name = _segments(entry['id'])
    parent = root
    for depth, segment in enumerate(folders, start=1):
        parent = _folder(parent, '/'.join([root.spz_uid(), *folders[:depth]]), segment)
    meta = {k: v for k, v in entry.items() if k not in ('id', 'info')}
    if issubclass(dataset_type, _LazyIndex):
        meta[_LOADED] = 'info' in entry
    uid = f"{root.spz_uid()}/{entry['id']}"
    dataset = _new_child(parent, name, lambda n: dataset_type(name=n, provider=provider, uid=uid, meta=meta))
    if 'info' in entry:
        fill_dataset(dataset, entry['info'])
    if 'title' in dataset.__dict__:
        dataset.__dict__.setdefault('description', dataset.__dict__['title'])


def _add_parameter(dataset: DatasetIndex, parameter: Mapping) -> None:
    meta = {**parameter, 'dataset': dataset.spz_uid(), 'start_date': dataset.__dict__.get('start_date'),
            'stop_date': dataset.__dict__.get('stop_date')}
    uid = f"{dataset.spz_uid()}/{parameter['name']}"
    _new_child(dataset, parameter['name'],
               lambda n: ParameterIndex(name=n, provider=dataset.spz_provider(), uid=uid, meta=meta))


def _segments(dataset_id: str) -> List[str]:
    return [s for s in dataset_id.split('/') if s] or [dataset_id]


def _dataset_meta(info: Mapping) -> dict:
    """``parameters[0]`` is always the time column: it gets no node but is kept to decode data responses."""
    meta = {k: v for k, v in info.items() if k not in _NOT_DATASET_META}
    meta['time_parameter'] = (info.get('parameters') or [None])[0]
    if 'startDate' in info and 'stopDate' in info:
        meta.update(start_date=normalized_time(info['startDate']), stop_date=normalized_time(info['stopDate']))
    return meta


def _folder(parent: SpeasyIndex, uid: str, segment: str) -> SpeasyIndex:
    return _child(parent, segment,
                  matches=lambda node: type(node) is SpeasyIndex and node.spz_uid() == uid,
                  make=lambda n: SpeasyIndex(name=n, provider=parent.spz_provider(), uid=uid))


def _new_child(parent: SpeasyIndex, raw_name: str, make: Callable[[str], SpeasyIndex]) -> SpeasyIndex:
    return _child(parent, raw_name, matches=lambda _: False, make=make)


def _child(parent: SpeasyIndex, raw_name: str, matches: Callable, make: Callable[[str], SpeasyIndex]) -> SpeasyIndex:
    """Different raw names can share a ``fix_name``, or clash with a metadata field: suffix with ``_`` until free."""
    name = fix_name(raw_name) or '_'
    while name in parent.__dict__:
        if matches(parent.__dict__[name]):
            return parent.__dict__[name]
        name += '_'
    parent.__dict__[name] = make(name)
    return parent.__dict__[name]
