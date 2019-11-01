from appdirs import *
from .cache import Cache

_cache = Cache(str(user_cache_dir("SciQLop","LPP")))
