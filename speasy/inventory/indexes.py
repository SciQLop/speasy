from typing import Optional
import json

__INDEXES_TYPES__ = {}


class SpeasyIndex:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        __INDEXES_TYPES__[cls.__name__] = cls

    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        if meta:
            self.__dict__.update(meta)
        self.provider = provider
        self.name = name
        self.type = self.__class__.__name__

    def __repr__(self):
        return f'<SpeasyIndex: {self.name}>'


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


class ComponentIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        super().__init__(name, provider, meta)

    def __repr__(self):
        return f'<ComponentIndex: {self.name}>'


class ParameterIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        super().__init__(name, provider, meta)

    def __repr__(self):
        return f'<ParameterIndex: {self.name}>'

    def __iter__(self):
        return [v for v in self.__dict__.values() if type(v) is ComponentIndex].__iter__()

    def __contains__(self, item: str or ComponentIndex):
        if type(item) is ComponentIndex:
            item = item.name
        return item in self.__dict__


class DatasetIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, meta: Optional[dict] = None):
        super().__init__(name, provider, meta)

    def __repr__(self):
        return f'<DatasetIndex: {self.name}>'

    def __iter__(self):
        return [v for v in self.__dict__.values() if type(v) is ParameterIndex].__iter__()

    def __contains__(self, item: str or ParameterIndex):
        if type(item) is ParameterIndex:
            item = item.name
        return item in self.__dict__


def to_dict(inventory_tree: SpeasyIndex or str):
    if type(inventory_tree) is str:
        return inventory_tree
    root = {key: to_dict(value) for key, value in inventory_tree.__dict__.items()}
    return root


def from_dict(inventory_tree: dict or str):
    if type(inventory_tree) is str:
        return inventory_tree
    idx_type = inventory_tree.pop("type")
    idx_name = inventory_tree.pop("name")
    idx_provider = inventory_tree.pop("provider")
    idx_meta = {key: from_dict(value) for key, value in inventory_tree.items()}
    root = __INDEXES_TYPES__.get(idx_type, SpeasyIndex)(name=idx_name, provider=idx_provider, meta=idx_meta)
    return root


def to_json(inventory_tree: SpeasyIndex):
    return json.dumps(to_dict(inventory_tree))


def from_json(inventory_tree: str):
    return from_dict(json.loads(inventory_tree))
