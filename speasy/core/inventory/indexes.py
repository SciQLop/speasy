from typing import Optional
import json

__INDEXES_TYPES__ = {}


class SpeasyIndex:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        __INDEXES_TYPES__[cls.__name__] = cls

    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        if meta:
            self.__dict__.update(meta)
        self.__spz_provider__ = provider
        self.__spz_name__ = name
        self.__spz_uid__ = uid
        self.__spz_type__ = self.__class__.__name__

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def clear(self):
        keys = list(self.__dict__.keys())
        for key in keys:
            if not key.startswith('__spz_'):
                self.__dict__.pop(key)

    def spz_provider(self):
        return self.__spz_provider__

    def spz_name(self):
        return self.__spz_name__

    def spz_uid(self):
        return self.__spz_uid__

    def spz_type(self):
        return self.__spz_type__

    def __repr__(self):
        return f'<SpeasyIndex: {self.spz_name()}>'


class TimetableIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    def __repr__(self):
        return f'<TimetableIndex: {self.spz_name()}>'


class CatalogIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    def __repr__(self):
        return f'<CatalogIndex: {self.spz_name()}>'


class ComponentIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    def __repr__(self):
        return f'<ComponentIndex: {self.spz_name()}>'


class ParameterIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    def __repr__(self):
        return f'<ParameterIndex: {self.spz_name()}>'

    def __iter__(self):
        return [v for v in self.__dict__.values() if type(v) is ComponentIndex].__iter__()

    def __contains__(self, item: str or ComponentIndex):
        if type(item) is ComponentIndex:
            item = item.name()
        return item in self.__dict__


class DatasetIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    def __repr__(self):
        return f'<DatasetIndex: {self.spz_name()}>'

    def __iter__(self):
        return [v for v in self.__dict__.values() if type(v) is ParameterIndex].__iter__()

    def __contains__(self, item: str or ParameterIndex):
        if type(item) is ParameterIndex:
            item = item.name()
        return item in self.__dict__


def to_dict(inventory_tree: SpeasyIndex or str):
    if isinstance(inventory_tree, SpeasyIndex):
        return {key: to_dict(value) for key, value in inventory_tree.__dict__.items()}
    elif type(inventory_tree) is not str:
        return str(inventory_tree)
    return inventory_tree


def from_dict(inventory_tree: dict or str):
    if type(inventory_tree) is str:
        return inventory_tree
    idx_type = inventory_tree.pop("__spz_type__")
    idx_name = inventory_tree.pop("__spz_name__")
    idx_provider = inventory_tree.pop("__spz_provider__")
    idx_uid = inventory_tree.pop("__spz_uid__")
    idx_meta = {key: from_dict(value) for key, value in inventory_tree.items()}
    root = __INDEXES_TYPES__.get(idx_type, SpeasyIndex)(name=idx_name, provider=idx_provider, uid=idx_uid,
                                                        meta=idx_meta)
    return root


def to_json(inventory_tree: SpeasyIndex, sort_keys=True):
    return json.dumps(to_dict(inventory_tree), sort_keys=sort_keys)


def from_json(inventory_tree: str):
    return from_dict(json.loads(inventory_tree))


def make_inventory_node(parent, ctor, name, provider, uid, **meta):
    if name not in parent.__dict__:
        parent.__dict__[name] = ctor(name=name, provider=provider, uid=uid, meta=meta)
    return parent.__dict__[name]


def inventory_has_changed(orig, new):
    if orig.__dict__.keys() != new.__dict__.keys():
        return True
    for orig_key, orig_value in orig.__dict__.items():
        if orig_key != 'build_date':
            if orig_key not in new.__dict__:
                return True
            if orig.__dict__[orig_key] != new.__dict__[orig_key]:
                return True
    return False
