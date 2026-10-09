from .cache import Cache, _release_at_exit
from ...config import cache as cache_cfg

_cache: Cache = Cache(cache_cfg.path())
_release_at_exit(_cache, "_data")
