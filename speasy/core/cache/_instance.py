from .cache import Cache
from ...config import cache as cache_cfg

_cache: Cache = Cache(cache_cfg.path())
