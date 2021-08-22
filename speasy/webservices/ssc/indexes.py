from speasy.inventory.indexes import ParameterIndex
from speasy.inventory import flat_inventories
from typing import Dict


class SscwebParameterIndex(ParameterIndex):
    def __init__(self, meta: Dict):
        name = meta.pop('Name')
        super(SscwebParameterIndex, self).__init__(name=name, provider="sscweb", meta=None)
        self.__dict__.update(meta)
        self.StartTime = self.StartTime[1]
        self.EndTime = self.EndTime[1]
        flat_inventories.ssc.parameters[self.Id] = self

    def product(self):
        return self.Id
