import diskcache as dc

from speasy.config import index as index_cfg


class SpeasyIndex:
    def __init__(self):
        self._index = dc.Index(index_cfg.path())

    def get(self, module, key, default=None):
        return self._index.get(f'{module}/{key}', default)

    def set(self, module, key, value):
        self._index[f'{module}/{key}'] = value

    def pop(self, module, key):
        return self._index.pop(f'{module}/{key}')

    def contains(self, module, key):
        return f'{module}/{key}' in self._index
