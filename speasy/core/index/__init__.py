from .speasy_index import SpeasyIndex as _SpeasyIndex
from ..cache.cache import _release_at_exit

index = _SpeasyIndex()
_release_at_exit(index, "_index")
