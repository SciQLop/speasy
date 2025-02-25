import json
from typing import Optional, Union

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
        return [v for v in self.__dict__.values() if isinstance(v, ComponentIndex)].__iter__()

    def __contains__(self, item: str or ComponentIndex):
        if isinstance(item, ComponentIndex):
            item = item.spz_uid()
        for member in self.__dict__.values():
            if isinstance(member, ComponentIndex):
                if member.spz_uid() == item:
                    return True
        return False


class ArgumentIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    def __repr__(self):
        return f'<ArgumentIndex: {self.spz_name()}>'


class ArgumentListIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    @property
    def _arguments(self):
        return [v for v in self.__dict__.values() if isinstance(v, ArgumentIndex)]

    def __repr__(self):
        return f'<ArgumentListIndex: {self.spz_name()}>'

    def __getitem__(self, item) -> ArgumentIndex:
        return self._arguments[item]

    def __len__(self):
        return len(self._arguments)

    def __iter__(self):
        return self._arguments.__iter__()


class TemplatedParameterIndex(ParameterIndex):
    __spz_arguments__: ArgumentListIndex

    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    def spz_arguments(self):
        return self.__spz_arguments__

    def __repr__(self):
        return f'<TemplatedParameterIndex: {self.spz_name()}>'


class DatasetIndex(SpeasyIndex):
    def __init__(self, name: str, provider: str, uid: str, meta: Optional[dict] = None):
        super().__init__(name, provider, uid, meta)

    def __repr__(self):
        return f'<DatasetIndex: {self.spz_name()}>'

    def __iter__(self):
        return [v for v in self.__dict__.values() if isinstance(v, ParameterIndex)].__iter__()

    def __contains__(self, item: str or ParameterIndex):
        if isinstance(item, ParameterIndex):
            item = item.spz_uid()
        for member in self.__dict__.values():
            if isinstance(member, ParameterIndex):
                if member.spz_uid() == item:
                    return True
        return False


def to_dict(inventory_tree: SpeasyIndex or str, version: int = 1):
    if isinstance(inventory_tree, SpeasyIndex):
        return {key: to_dict(value, version=version) for key, value in inventory_tree.__dict__.items()}
    elif version <= 1:
        if type(inventory_tree) is not str:
            inventory_tree = str(inventory_tree)
    else:
        if type(inventory_tree) in [list, tuple, set]:
            return type(inventory_tree)([to_dict(value, version) for value in inventory_tree])
        if type(inventory_tree) is dict:
            return {key: to_dict(value, version) for key, value in inventory_tree.items()}
        if type(inventory_tree) not in [str, int, float, bool, type(None)]:
            return str(inventory_tree)

    return inventory_tree


def from_dict(inventory_tree: dict or str, version: int = 1):
    if version <= 1:
        if type(inventory_tree) is str:
            return inventory_tree
    else:
        if type(inventory_tree) in [str, int, float, bool, type(None), list, tuple, set]:
            return inventory_tree
        if type(inventory_tree) is dict and "__spz_type__" not in inventory_tree:
            return inventory_tree
    idx_type = inventory_tree.pop("__spz_type__")
    idx_name = inventory_tree.pop("__spz_name__")
    idx_provider = inventory_tree.pop("__spz_provider__")
    idx_uid = inventory_tree.pop("__spz_uid__")
    idx_meta = {key: from_dict(value, version) for key, value in inventory_tree.items()}
    root = __INDEXES_TYPES__.get(idx_type, SpeasyIndex)(name=idx_name, provider=idx_provider, uid=idx_uid,
                                                        meta=idx_meta)
    return root


def to_json(inventory_tree: SpeasyIndex, sort_keys=True, version: int = 1):
    return json.dumps(to_dict(inventory_tree, version), sort_keys=sort_keys)


def from_json(inventory_tree: str, version: int = 1):
    return from_dict(json.loads(inventory_tree), version)


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


AnyProductIndex = Union[
    ParameterIndex, TemplatedParameterIndex, DatasetIndex, TimetableIndex, CatalogIndex, ComponentIndex]
