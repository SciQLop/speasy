"""A persistent, exportable store of the data a study used (GH #122), see ``DataIndex``."""
import inspect
import logging
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple
from urllib.parse import unquote

try:
    import pysciqlop_cache
except ImportError as e:  # pragma: no cover - WASM has no pysciqlop-cache wheel
    raise ImportError("DataIndex needs pysciqlop-cache and msgspec, which Speasy doesn't install on this "
                      "platform (Pyodide)") from e

from speasy.core import AnyDateTimeType, make_utc_datetime
from speasy.core.cache import CACHE_ALLOWED_KWARGS
from speasy.core.cache._providers_caches import PROVISIONAL_FRAGMENT_LIFETIME
from speasy.core.dataprovider import GET_DATA_ALLOWED_KWARGS, provider_class
from speasy.core.proxy import PROXY_ALLOWED_KWARGS
from speasy.core.requests_scheduling.request_dispatch import get_data as _spz_get_data, provider_and_product
from speasy.products.variable import SpeasyVariable, from_dictionary, merge
from . import _archive
from ._keys import (FRAGMENT, canonical_provider, data_key, fragments, options_hash, parse_data_key, request_key,
                    runs)
from ._storable import Serializer, from_storable, to_storable

log = logging.getLogger(__name__)

FORMAT = 1
_META = "__meta__"
_DB_FILE = "sciqlop-cache.db"
# accepted by most providers, but they only change how the data travels, so they never are request options
_TRANSPORT_KWARGS = {'method', 'if_newer_than', 'debug', 'format'}
# (index path, data key) of the live-edge fragments already warned about, so an offline plotting loop warns once
_warned_live_edges = set()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class Entry(NamedTuple):
    """One stored fragment. ``variable`` is None for a fragment known to hold no data."""
    fetched_at: int
    variable: Optional[SpeasyVariable]


def _split(product: str) -> Tuple[str, str]:
    provider, sep, name = product.partition('/')
    if not sep:
        raise ValueError(f"{product!r} is not a product path, expected '<provider>/<product>', e.g. 'cda/AC_H0_MFI/BGSEc'")
    return provider, name


def _product_path(product) -> str:
    provider, name = provider_and_product(product)
    return f"{provider}/{name}"


def _check_kwargs(provider: type, kwargs: dict):
    # checked here, not left to the provider: a covered request never reaches it, and a misspelt option would then
    # silently give the default's data
    known = {*GET_DATA_ALLOWED_KWARGS, *CACHE_ALLOWED_KWARGS, *PROXY_ALLOWED_KWARGS, *_TRANSPORT_KWARGS,
             *(name for name, p in inspect.signature(provider.request_options).parameters.items()
               if p.kind is not inspect.Parameter.VAR_KEYWORD)}
    if unknown := sorted(set(kwargs) - known):
        raise TypeError(f"Unexpected keyword argument(s) {unknown} for {provider.NAME}, "
                        f"allowed keyword arguments are {sorted(known)}")


def _is_live_edge(fragment: datetime, entry: Entry, now: datetime) -> bool:
    """A stored fragment fetched before its end may still grow: refetch it, but at most once an hour."""
    fetched = datetime.fromtimestamp(entry.fetched_at, tz=timezone.utc)
    return fragment + FRAGMENT > fetched and now - fetched >= PROVISIONAL_FRAGMENT_LIFETIME


def _pieces(variable: Optional[SpeasyVariable], run: List[datetime]) -> Dict[datetime, Optional[SpeasyVariable]]:
    """Cuts a run's result into its fragments; a fragment without rows is None."""
    pieces = {fragment: variable[fragment:fragment + FRAGMENT] if variable is not None else None for fragment in run}
    return {fragment: piece.copy() if piece is not None and len(piece) else None for fragment, piece in pieces.items()}


def _refuse_foreign_folder(path: str):
    if os.path.isdir(path) and os.listdir(path) and not os.path.exists(os.path.join(path, _DB_FILE)):
        raise ValueError(f"{path} is not a Speasy data index, it holds other files: give an empty or a new folder")


def _open_store(path: str):
    try:
        return pysciqlop_cache.Index(path, serializer=Serializer())
    except ValueError as e:  # pysciqlop-cache refuses a store written with another serializer
        raise ValueError(f"{path} is not a Speasy data index ({e}). Speasy only opens data indexes it wrote itself: "
                         f"it never decodes pickle or msgspec data from elsewhere.") from e


class DataIndex:
    """A folder holding exactly the data put in it: it never expires, and can be exported and imported.

    A fragment once stored, even known to be empty, is only downloaded again when asked to (``refresh=True``,
    ``update_all_data``), except the last one of a dataset, which may still grow and is refetched once an hour."""

    def __init__(self, path: str):
        self.path = os.path.expanduser(path)
        _refuse_foreign_folder(self.path)
        self._store = _open_store(self.path)
        self._check_meta()

    def _check_meta(self):
        import speasy
        meta = self._store.get(_META)
        if meta is None:
            if next(iter(self._store.iterkeys()), None) is not None:
                raise ValueError(f"{self.path} is not a Speasy data index: it has entries but no {_META}")
            self._store[_META] = {"format": FORMAT, "fragment_hours": 24, "created_by": speasy.__version__}
        elif not isinstance(meta, dict):
            raise ValueError(f"{self.path} is not a Speasy data index: its {_META} is not a dict")
        elif meta.get("format") != FORMAT:
            raise ValueError(f"{self.path} uses data index format {meta.get('format')}, written by a newer Speasy "
                             f"({meta.get('created_by')}): upgrade Speasy to read it")

    def close(self):
        self._store.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def write_fragment(self, product: str, options: dict, fragment: datetime, variable: Optional[SpeasyVariable],
                       fetched_at: int):
        provider, name = _split(product)
        digest = options_hash(options)
        # set() is idempotent: no read-then-write on every request
        self._store[request_key(provider, name, digest)] = {"options": options}
        stored = to_storable(variable.to_dictionary()) if variable is not None else None
        self._store[data_key(provider, name, digest, fragment)] = {"fetched_at": int(fetched_at), "variable": stored}

    def read_fragment(self, product: str, options: dict, fragment: datetime) -> Optional[Entry]:
        provider, name = _split(product)
        raw = self._store.get(data_key(provider, name, options_hash(options), fragment))
        if raw is None:
            return None
        variable = raw["variable"]
        return Entry(raw["fetched_at"], from_dictionary(from_storable(variable)) if variable is not None else None)

    def requests(self) -> List[dict]:
        """Every product and options this index stores data for."""
        # simplify: scans every key; a prefix query in pysciqlop-cache would read only the requests/ ones
        found = []
        for key in self._store.iterkeys():
            if key.startswith("requests/"):
                _, provider, product, _ = key.split('/')
                found.append({"provider": provider, "product": unquote(product),
                              "options": self._store[key]["options"]})
        return found

    def summary(self) -> List[dict]:
        """Per product and options: the spans of days with data, and of days known to hold none."""
        days = defaultdict(lambda: ([], []))
        for key in self._store.iterkeys():
            if (parsed := parse_data_key(key)) is not None:
                known_empty = self._store[key]["variable"] is None
                days[(parsed.provider, parsed.product, parsed.options_digest)][known_empty].append(parsed.fragment)
        return [{"product": f"{provider}/{product}",
                 "options": self._store[request_key(provider, product, digest)]["options"],
                 "data": _spans(with_data), "empty": _spans(empty)}
                for (provider, product, digest), (with_data, empty) in sorted(days.items())]

    def disk_size(self) -> int:
        return self._store.volume()

    def get_data(self, product, start: AnyDateTimeType, stop: AnyDateTimeType, refresh: bool = False,
                 **kwargs) -> Optional[SpeasyVariable]:
        """Like ``speasy.get_data``, but served from the index, which downloads only what it doesn't hold yet.

        ``refresh=True`` downloads the whole range again, past the provider cache, and replaces what the index held,
        even with nothing if the provider has no data there any more."""
        path = _product_path(product)
        _check_kwargs(provider_class(_split(path)[0]), kwargs)
        start, stop, now = make_utc_datetime(start), make_utc_datetime(stop), _now()
        if stop <= start:
            raise ValueError(f"stop ({stop}) must be after start ({start})")
        if start >= now:
            return None
        options = to_storable(provider_class(_split(path)[0]).request_options(**kwargs))
        grid = fragments(start, stop, now)
        entries = {fragment: self.read_fragment(path, options, fragment) for fragment in grid}
        missing = grid if refresh else [fragment for fragment, entry in entries.items() if entry is None]
        live = [] if refresh else [fragment for fragment, entry in entries.items()
                                   if entry is not None and _is_live_edge(fragment, entry, now)]
        if refresh:
            kwargs = {**kwargs, 'force_refresh': True}
        entries.update(self._fetch_missing(path, options, missing, now, kwargs))
        entries.update(self._refetch_live_edges(path, options, live, now, kwargs))
        return _merged([entry.variable for entry in entries.values() if entry is not None], start, stop)

    def _fetch_run(self, path: str, options: dict, run: List[datetime], now: datetime,
                   kwargs: dict) -> Dict[datetime, Optional[SpeasyVariable]]:
        variable = _spz_get_data(path, run[0], min(run[-1] + FRAGMENT, now), **kwargs)
        if variable is not None and not isinstance(variable, SpeasyVariable):
            raise TypeError(f"{path} gives a {type(variable).__name__}: a data index stores time series only")
        return _pieces(variable, run)

    def _store_pieces(self, path: str, options: dict, pieces: Dict[datetime, Optional[SpeasyVariable]],
                      now: datetime) -> Dict[datetime, Entry]:
        with self._store.transact():
            for fragment, piece in pieces.items():
                self.write_fragment(path, options, fragment, piece, fetched_at=int(now.timestamp()))
        return {fragment: Entry(int(now.timestamp()), piece) for fragment, piece in pieces.items()}

    def _fetch_missing(self, path: str, options: dict, missing: List[datetime], now: datetime,
                       kwargs: dict) -> Dict[datetime, Entry]:
        """Fetches and stores every run; one failing run doesn't stop the others, its error is raised after them."""
        fetched, errors = {}, []
        for run in runs(missing):
            try:
                fetched.update(self._store_pieces(path, options, self._fetch_run(path, options, run, now, kwargs), now))
            except Exception as e:  # pylint: disable=broad-except
                errors.append(e)
        if errors:
            raise errors[0]
        return fetched

    def _refetch_live_edges(self, path: str, options: dict, live: List[datetime], now: datetime,
                            kwargs: dict) -> Dict[datetime, Entry]:
        """An automatic refetch never destroys data: on failure, or if it finds nothing, the stored rows stay."""
        refetched = {}
        for run in runs(live):
            try:
                pieces = self._fetch_run(path, options, run, now, kwargs)
            except Exception as e:  # pylint: disable=broad-except
                self._warn_once(path, options, run, e)
                continue
            refetched.update(self._store_pieces(path, options, {f: p for f, p in pieces.items() if p is not None}, now))
        return refetched

    def _warn_once(self, path: str, options: dict, run: List[datetime], error: Exception):
        key = (self.path, path, options_hash(options), run[0])
        if key not in _warned_live_edges:
            _warned_live_edges.add(key)
            log.warning(f"Could not refresh {path} from {run[0]}, which may have grown since it was stored "
                        f"({error}): using the stored data")

    def export_data(self, tar_path: str):
        """Writes the whole index to ``tar_path``, for ``import_data`` on another machine.

        It copies the index into a temporary folder first, so it needs that much free temporary space."""
        with tempfile.TemporaryDirectory() as tmp:
            with DataIndex(os.path.join(tmp, "index")) as snapshot, snapshot._store.transact():
                for key in self._store.iterkeys():
                    snapshot._store[key] = self._store[key]
            # closed: SQLite has folded its write-ahead log into the database, no -wal/-shm left to ship
            _archive.pack(snapshot.path, tar_path)

    def import_data(self, source: str):
        """Adds what ``source``, a tar from ``export_data`` or an index folder, holds. When both hold a fragment, the
        one fetched last wins."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = source if os.path.isdir(source) else _archive.unpack(source, tmp)
            if not os.path.exists(os.path.join(folder, _DB_FILE)):
                raise ValueError(f"{source} is not a Speasy data index")
            with DataIndex(folder) as other:
                self._merge(other)

    def _merge(self, other: "DataIndex"):
        ours, theirs = self._store[_META].get("fragment_hours"), other._store[_META].get("fragment_hours")
        if ours != theirs:
            raise ValueError(f"{other.path} uses {theirs} h fragments and this index {ours} h: they can't be merged")
        # the write transaction is taken before reading, so a concurrent writer can't slip in between
        with self._store.transact():
            for key in other._store.iterkeys():
                if key != _META and _is_newer(other._store[key], self._store.get(key), key):
                    self._store[key] = other._store[key]

    def update_all_data(self, products: Optional[Iterable] = None):
        """Downloads again everything the index holds, or only ``products`` (any name of their provider), past the
        provider cache. Fragments known to be empty are checked again too."""
        wanted = {_canonical_path(product) for product in products} if products is not None else None
        stored = defaultdict(list)
        for key in self._store.iterkeys():
            if (parsed := parse_data_key(key)) is not None:
                stored[(parsed.provider, parsed.product, parsed.options_digest)].append(parsed.fragment)
        errors = []
        for (provider, product, digest), starts in stored.items():
            if wanted is None or f"{provider}/{product}" in wanted:
                options = self._store[request_key(provider, product, digest)]["options"]
                errors += self._refresh_runs(f"{provider}/{product}", options, sorted(starts))
        if errors:
            raise errors[0]

    def _refresh_runs(self, path: str, options: dict, starts: List[datetime]) -> List[Exception]:
        errors = []
        for run in runs(starts):
            try:
                self.get_data(path, run[0], run[-1] + FRAGMENT, refresh=True, **options)
            except Exception as e:  # pylint: disable=broad-except
                errors.append(e)
        return errors


def _is_newer(theirs, ours, key: str) -> bool:
    if not key.startswith("data/"):
        return True
    if not (isinstance(theirs, dict) and isinstance(theirs.get("fetched_at"), int)):
        raise ValueError(f"Refusing a malformed data index entry {key!r}")
    return ours is None or theirs["fetched_at"] > ours["fetched_at"]


def _spans(starts: List[datetime]) -> List[Tuple[datetime, datetime]]:
    return [(run[0], run[-1] + FRAGMENT) for run in runs(sorted(starts))]


def _canonical_path(product) -> str:
    provider, name = _split(_product_path(product))
    return f"{canonical_provider(provider)}/{name}"


def _merged(variables: List[Optional[SpeasyVariable]], start: datetime, stop: datetime) -> Optional[SpeasyVariable]:
    merged = merge([v for v in variables if v is not None])
    if merged is None or len(merged) == 0:
        return None
    trimmed = merged[start:stop]
    return trimmed if len(trimmed) else None
