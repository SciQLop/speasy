from typing import Tuple
from types import SimpleNamespace
from speasy.inventory.indexes import ParameterIndex, DatasetIndex, ComponentIndex
from speasy.inventory import flat_inventories


class CDAIndex:
    def __init__(self, id: str):
        self._id = id

    def dl_kw_args(self):
        return {'xmlid': self._id}

    def cda_id(self):
        return self._id


class CDAPathIndex(SimpleNamespace):
    def __init__(self, **meta):
        super().__init__(**meta)


class CDAComponentIndex(CDAIndex, ComponentIndex):  # lgtm [py/conflicting-attributes]
    def __init__(self, **meta):
        _id = meta.pop('serviceprovider_ID')
        name = meta.pop('name')
        ComponentIndex.__init__(self=self, name=name, provider="cdaweb", meta=meta)
        CDAIndex.__init__(self=self, id=_id)
        flat_inventories.cda.components[_id] = self


class CDAParameterIndex(CDAIndex, ParameterIndex):  # lgtm [py/conflicting-attributes]
    def __init__(self, name, dataset, **meta):
        name = name
        self.dataset = dataset
        ParameterIndex.__init__(self=self, name=name, provider="cdaweb", meta=meta)
        CDAIndex.__init__(self=self, id=name)
        flat_inventories.cda.parameters[name] = self

    def product(self):
        return f"{self.dataset}/{self.name}"


class CDADatasetIndex(CDAIndex, DatasetIndex):  # lgtm [py/conflicting-attributes]

    def __init__(self, **meta):
        _id = meta.pop('serviceprovider_ID')
        name = meta.pop('name')
        DatasetIndex.__init__(self=self, name=name, provider="cdaweb", meta=meta)
        CDAIndex.__init__(self=self, id=_id)
        flat_inventories.cda.datasets[_id] = self


def to_dataset_and_variable(index_or_str: CDAParameterIndex or str) -> Tuple[str, str]:
    if type(index_or_str) is str:
        parts = index_or_str.split('/')
        assert len(parts) == 2
        return parts[0], parts[1]
    if type(index_or_str) is CDAParameterIndex:
        parts = index_or_str.product().split('/')
        assert len(parts) == 2
        return parts[0], parts[1]
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")
