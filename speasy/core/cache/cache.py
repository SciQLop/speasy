import os
import re
import shutil
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Union

try:
    import pysciqlop_cache as sc
except ImportError:  # pragma: no cover - platform-specific (WASM has no wheel)
    # No compiled backend (e.g. WASM/Pyodide): fall back to a no-op cache so
    # importing Speasy still works; caching is simply disabled.
    from . import _noop_cache as sc

from .version import str_to_version, version_to_str, Version
from speasy.config import cache as cache_cfg

cache_version = str_to_version("3.0")

log = logging.getLogger(__name__)


class CacheItem:
    def __init__(self, data, version, lifetime=None):
        self.data = data
        self.version = version
        if lifetime is not None and isinstance(lifetime, (float, int)):
            lifetime = timedelta(seconds=lifetime)
        self.lifetime = lifetime
        self.created = datetime.now(tz=timezone.utc)

    def bump_creation_time(self) -> "CacheItem":
        self.created = datetime.now(tz=timezone.utc)
        return self

    def __setstate__(self, state):
        self.data = state["data"]
        self.version = state["version"]
        self.lifetime = state.get("lifetime", None)
        self.created = state.get("created", datetime.now(tz=timezone.utc))

    def is_expired(self) -> bool:
        if isinstance(self.lifetime, timedelta):
            return datetime.now(tz=timezone.utc) > (self.created + self.lifetime)
        else:
            return False


def _is_already_sciqlop_cache_layout(p: Path) -> bool:
    return (p / "sciqlop-cache.db").is_file() or bool(list(p.glob("*/sciqlop-cache.db")))


def _is_legacy_diskcache_layout(p: Path) -> bool:
    if not p.exists():
        return False
    # A directory already on the new backend can still have a stray ``cache.db``
    # left over from an older pysciqlop-cache release (before that file was
    # renamed to ``sciqlop-cache.db``). Presence of the new backend's own file is
    # definitive: never treat such a directory as needing (re-)migration.
    if _is_already_sciqlop_cache_layout(p):
        return False
    return (p / "cache.db").is_file() or bool(list(p.glob("*/cache.db")))


def _migrate_legacy_diskcache(full_path: str) -> bool:
    """Detect a legacy diskcache layout at ``full_path`` and migrate it to
    sciqlop-cache format. Returns True if a migration was performed.

    The legacy cache is renamed to ``<full_path>.diskcache.backup`` and the new
    cache is written directly at ``full_path`` (sciqlop-cache references external
    value files by absolute path, so the destination cannot be relocated after
    writing). On any failure the legacy cache is restored.

    For large caches this can take minutes — a one-time cost on first launch
    after upgrading. The legacy backup is kept so the user can verify and
    delete it manually.
    """
    p = Path(full_path)
    if not _is_legacy_diskcache_layout(p):
        return False

    backup = Path(f"{p}.diskcache.backup")

    if backup.exists():
        log.warning(
            f"Legacy cache backup already present at {backup}; "
            f"skipping auto-migration. Move or remove it to retry."
        )
        return False

    try:
        from pysciqlop_cache.migrate import migrate
    except ImportError as e:
        log.error(
            f"Detected legacy diskcache layout at {p} but cannot migrate "
            f"(missing dependency: {e}). Install diskcache once to allow "
            f"migration, or delete {p} to start fresh."
        )
        return False

    log.warning(
        f"Detected legacy diskcache layout at {p}; migrating to sciqlop-cache. "
        f"This is a one-time operation and may take several minutes for large caches."
    )
    # sciqlop-cache stores large values as external files referenced by
    # absolute path, so a migrated cache cannot be relocated afterwards.
    # Rename the legacy cache out of the way, then migrate straight into the
    # final path; restore the legacy cache on any failure.
    os.rename(str(p), str(backup))
    try:
        result = migrate(str(backup), str(p))
    except ImportError as e:
        if p.exists():
            shutil.rmtree(str(p))
        os.rename(str(backup), str(p))
        log.error(
            f"Detected legacy diskcache layout at {p} but cannot migrate "
            f"(missing dependency: {e}). Install diskcache once to allow "
            f"migration, or delete {p} to start fresh."
        )
        return False
    except Exception:
        if p.exists():
            shutil.rmtree(str(p))
        os.rename(str(backup), str(p))
        raise

    log.info(
        f"Migration complete: {result['migrated']} entries in "
        f"{result['elapsed_secs']}s. Legacy cache preserved at {backup}; "
        f"delete it once you've verified the new cache works."
    )
    return True


def _warn_if_backup_present(full_path: str) -> None:
    """Log a reminder if a migration backup still sits next to ``full_path``.

    Called on every construction of a cache/index built at this path, so the
    reminder keeps showing up (once per import) until the user actually
    deletes the backup with :func:`delete_migration_backups`.
    """
    backup = Path(f"{full_path}.diskcache.backup")
    if backup.exists():
        log.warning(
            f"A legacy cache backup from migrating to sciqlop-cache is still "
            f"present at {backup}. Once you've verified the new cache works, "
            f"delete it with speasy.core.cache.delete_migration_backups()."
        )


def _known_migratable_paths() -> List[str]:
    """Paths of every cache/index Speasy builds that could carry a legacy
    diskcache layout -- i.e. every call site of :func:`_migrate_legacy_diskcache`.
    """
    from speasy.config import index as index_cfg
    return [f"{cache_cfg.path()}/Cache", index_cfg.path()]


def migration_backups() -> List[str]:
    """List legacy diskcache backups left over from migrating to sciqlop-cache.

    Returns
    -------
    List[str]
        Paths to backup directories that currently exist on disk.
    """
    return [
        backup for backup in (f"{p}.diskcache.backup" for p in _known_migratable_paths())
        if os.path.isdir(backup)
    ]


def delete_migration_backups() -> List[str]:
    """Delete legacy diskcache backups left over from migrating to sciqlop-cache.

    Safe to call at any time: only removes the ``<path>.diskcache.backup``
    directories created by the one-time migration, never a live cache.

    Returns
    -------
    List[str]
        Paths that were actually deleted.
    """
    deleted = []
    for backup in migration_backups():
        shutil.rmtree(backup)
        deleted.append(backup)
        log.info(f"Deleted migration backup at {backup}")
    return deleted


class Cache:
    __slots__ = ["cache_file", "_data", "cache_type"]

    def __init__(self, cache_path: str = "", cache_type: str = "Cache"):
        full_path = f"{cache_path}/{cache_type}"
        _migrate_legacy_diskcache(full_path)
        _warn_if_backup_present(full_path)

        if cache_type == "Fanout":
            self._data = sc.FanoutCache(
                cache_path=full_path, shard_count=8, max_size=cache_cfg.size()
            )
        elif cache_type == "Cache":
            self._data = sc.Cache(cache_path=full_path, max_size=cache_cfg.size())
        else:
            raise ValueError(f"Unimplemented cache type: {cache_type}")

        self.cache_type = cache_type
        self._data.reset_stats()
        if self.version < cache_version:
            self._data.clear()
            self.version = cache_version

    @property
    def version(self):
        return str_to_version(self._data.get("cache/version", default="0.0.0"))

    @version.setter
    def version(self, v: Union[str, Version]):
        self._data["cache/version"] = v if type(v) is str else version_to_str(v)

    def disk_size(self):
        return self._data.volume()

    def stats(self):
        s = self._data.stats()
        return {
            "hit": s["hits"],
            "misses": s["misses"],
        }

    def __len__(self):
        return len(self._data)

    def keys(self):
        return list(self._data)

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def set(self, key, value, expire=None, tag: Optional[str] = None):
        self._data.set(key, value, expire=expire, tag=tag)

    def add(self, key, value, expire=None, tag: Optional[str] = None):
        return self._data.add(key, value, expire=expire, tag=tag)

    def get(self, key, default_value=None):
        return self._data.get(key, default_value)

    def incr(self, key, delta=1, default=0):
        return self._data.incr(key, delta, default=default)

    def drop(self, key):
        self._data.delete(key)

    def evict_tag(self, tag: str):
        return self._data.evict_tag(tag)

    def drop_matching_entries(self, pattern: Union[str, re.Pattern]):
        """Drop all cache entries that match a given pattern

        Parameters
        ----------
        pattern : str or re.Pattern
            The pattern to match cache keys against
        """
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        for key in filter(pattern.match, self.keys()):
            log.debug(f"Dropping cache entry {key}")
            self.drop(key)

    @contextmanager
    def transact(self, key: Optional[str] = None):
        """Open a transaction context.

        For a single Cache the ``key`` argument is ignored. For a FanoutCache
        the transaction is per-shard and ``key`` selects the shard — atomicity
        only applies within that shard, so all operations in the block must
        target the same shard key.
        """
        if self.cache_type == "Fanout":
            if key is None:
                raise ValueError(
                    "FanoutCache.transact requires a key to select a shard"
                )
            with self._data.transact(key):
                yield
        else:
            with self._data.transact():
                yield

    @contextmanager
    def lock(self, key: str):
        lock = sc.Lock(self._data, key)
        lock.acquire()
        try:
            yield lock
        finally:
            lock.release()
