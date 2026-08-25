try:
    import pysciqlop_cache as sc
except ImportError:  # pragma: no cover - platform-specific (WASM has no wheel)
    # No compiled backend (e.g. WASM/Pyodide): fall back to a no-op store.
    from speasy.core.cache import _noop_cache as sc

from speasy.config import cache as cache_cfg
from speasy.config import index as index_cfg
from speasy.core.cache.cache import _migrate_legacy_diskcache, _warn_if_backup_present, _open_or_recover


class SpeasyIndex:
    def __init__(self):
        path = index_cfg.path()
        _migrate_legacy_diskcache(path, move=cache_cfg.migrate_by_moving())
        _warn_if_backup_present(path)
        self._index = _open_or_recover(lambda: sc.Index(path=path), path, "index")

    def get(self, module, key, default=None):
        return self._index.get(f'{module}/{key}', default)

    def set(self, module, key, value):
        self._index[f'{module}/{key}'] = value

    def pop(self, module, key):
        return self._index.pop(f'{module}/{key}')

    def contains(self, module, key):
        return f'{module}/{key}' in self._index
