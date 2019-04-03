import os
from pathlib import Path
from typing import List, Optional

import diskcache as dc
from appdirs import *
from .cache import Cache

cache = Cache(str(user_cache_dir("SciQLop","LPP")))
