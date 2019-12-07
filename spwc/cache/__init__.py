from appdirs import user_cache_dir
from .cache import Cache

_cache = Cache(str(user_cache_dir("SciQLop", "LPP")))
