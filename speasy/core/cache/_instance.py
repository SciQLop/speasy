from ...config import cache as cache_cfg
from .cache import Cache

_cache: Cache = Cache(cache_cfg.path())
