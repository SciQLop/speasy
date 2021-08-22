from typing import Optional, Any


class SpeasyIndex:
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        self.provider = provider
        self.name = name
        if meta:
            self.__dict__.update(meta)

    def dl_kw_args(self):
        raise NotImplementedError("You have to override this method")


class TimetableIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        super().__init__(name, provider, meta)

    def __repr__(self):
        return f'<TimetableIndex: {self.name}>'


class CatalogIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        super().__init__(name, provider, meta)

    def __repr__(self):
        return f'<CatalogIndex: {self.name}>'


class DatasetIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        super().__init__(name, provider, meta)

    def __repr__(self):
        return f'<DatasetIndex: {self.name}>'


class ParameterIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        super().__init__(name, provider, meta)

    def __repr__(self):
        return f'<ParameterIndex: {self.name}>'

    def product(self):
        raise NotImplementedError("You have to override this method")


class ComponentIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        super().__init__(name, provider, meta)

    def __repr__(self):
        return f'<ComponentIndex: {self.name}>'
