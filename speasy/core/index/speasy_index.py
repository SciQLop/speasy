from typing import Union
import diskcache as dc
from speasy.config import index_path


class SpeasyIndex:
    def __init__(self):
        self._index = dc.Index(index_path.get())

    def get(self, module, key, default=None):
        return self._index.get(f'{module}/{key}', default)

    def set(self, module, key, value):
        self._index[f'{module}/{key}'] = value
