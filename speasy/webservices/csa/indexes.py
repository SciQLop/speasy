from typing import Tuple
from types import SimpleNamespace
from speasy.inventory.indexes import ParameterIndex, DatasetIndex
from speasy.inventory import flat_inventories


class CSAIndex:
    def __init__(self, id: str):
        self._id = id

    def dl_kw_args(self):
        return {'xmlid': self._id}

    def CSA_id(self):
        return self._id


class CSAPathIndex(SimpleNamespace):
    def __init__(self, **meta):
        super().__init__(**meta)


class CSAParameterIndex(CSAIndex, ParameterIndex):  # lgtm [py/conflicting-attributes]
    def __init__(self, **meta):
        _id = meta.pop('parameter_id')
        name = _id
        self.dataset = meta['dataset_id']
        ParameterIndex.__init__(self=self, name=name, provider="csa", meta=meta)
        CSAIndex.__init__(self=self, id=name)
        flat_inventories.csa.parameters[name] = self

    def product(self):
        return f"{self.dataset}/{self.name}"


class CSADatasetIndex(CSAIndex, DatasetIndex):  # lgtm [py/conflicting-attributes]

    def __init__(self, **meta):
        _id = meta.pop('dataset_id')
        name = _id
        DatasetIndex.__init__(self=self, name=name, provider="csa", meta=meta)
        CSAIndex.__init__(self=self, id=_id)
        flat_inventories.csa.datasets[_id] = self

def to_dataset_and_variable(index_or_str: CSAParameterIndex or str) -> Tuple[str, str]:
    if type(index_or_str) is str:
        parts = index_or_str.split('/')
        assert len(parts) == 2
        return parts[0], parts[1]
    if type(index_or_str) is CSAParameterIndex:
        parts = index_or_str.product().split('/')
        assert len(parts) == 2
        return parts[0], parts[1]
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")
