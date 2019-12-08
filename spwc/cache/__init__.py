from .cache import Cache
from ..config import cache_path

_cache = Cache(cache_path.get())
