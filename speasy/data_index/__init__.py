"""A persistent, exportable store of the data a study used (GH #122), see ``DataIndex``."""
import os
from datetime import datetime
from typing import List, NamedTuple, Optional, Tuple
from urllib.parse import unquote

try:
    import pysciqlop_cache
except ImportError as e:  # pragma: no cover - WASM has no pysciqlop-cache wheel
    raise ImportError("DataIndex needs pysciqlop-cache and msgspec, which Speasy doesn't install on this "
                      "platform (Pyodide)") from e

from speasy.products.variable import SpeasyVariable, from_dictionary
from ._keys import data_key, options_hash, request_key
from ._storable import Serializer, from_storable, to_storable

FORMAT = 1
_META = "__meta__"
_DB_FILE = "sciqlop-cache.db"


class Entry(NamedTuple):
    """One stored fragment. ``variable`` is None for a fragment known to hold no data."""
    fetched_at: int
    variable: Optional[SpeasyVariable]


def _split(product: str) -> Tuple[str, str]:
    provider, sep, name = product.partition('/')
    if not sep:
        raise ValueError(f"{product!r} is not a product path, expected '<provider>/<product>', e.g. 'cda/AC_H0_MFI/BGSEc'")
    return provider, name


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
    """A folder holding exactly the data put in it: it never expires, and can be exported and imported."""

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
