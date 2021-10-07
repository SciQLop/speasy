from typing import Dict
from types import SimpleNamespace
from speasy.inventory.indexes import CatalogIndex, ParameterIndex, TimetableIndex, DatasetIndex, ComponentIndex
from speasy.inventory import flat_inventories


def to_xmlid(index_or_str) -> str:
    if type(index_or_str) is str:
        return index_or_str
    if type(index_or_str) is dict and "xmlid" in index_or_str:
        return index_or_str['xmlid']
    if hasattr(index_or_str, 'xmlid'):
        return index_or_str.xmlid
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")


class AMDAIndex:
    def __init__(self, xmlid: str, is_public=True):
        self.xmlid = xmlid
        self.is_public = is_public

    def dl_kw_args(self):
        return {'xmlid': self.xmlid}


class AMDATimetableIndex(AMDAIndex, TimetableIndex):  # lgtm [py/conflicting-attributes]
    def __init__(self, meta: Dict, is_public=True):
        xmlid = meta.pop('xmlid')
        name = meta.pop('name')
        TimetableIndex.__init__(self=self, name=name, provider="amda", meta=meta)
        AMDAIndex.__init__(self=self, xmlid=xmlid, is_public=is_public)
        flat_inventories.amda.timetables[xmlid] = self


class AMDACatalogIndex(AMDAIndex, CatalogIndex):  # lgtm [py/conflicting-attributes]
    def __init__(self, meta: Dict, is_public=True):
        xmlid = meta.pop('xmlid')
        name = meta.pop('name')
        CatalogIndex.__init__(self=self, name=name, provider="amda", meta=meta)
        AMDAIndex.__init__(self=self, xmlid=xmlid, is_public=is_public)
        flat_inventories.amda.catalogs[self.xmlid] = self


class AMDAComponentIndex(AMDAIndex, ComponentIndex):  # lgtm [py/conflicting-attributes]
    def __init__(self, meta: Dict, is_public=True):
        xmlid = meta.pop('xmlid')
        name = meta.pop('name')
        ComponentIndex.__init__(self=self, name=name, provider="amda", meta=meta)
        AMDAIndex.__init__(self=self, xmlid=xmlid, is_public=is_public)
        flat_inventories.amda.components[xmlid] = self


class AMDAParameterIndex(AMDAIndex, ParameterIndex):  # lgtm [py/conflicting-attributes]
    def __init__(self, meta: Dict, is_public=True):
        xmlid = meta.pop('xmlid')
        name = meta.pop('name')
        ParameterIndex.__init__(self=self, name=name, provider="amda", meta=meta)
        AMDAIndex.__init__(self=self, xmlid=xmlid, is_public=is_public)
        flat_inventories.amda.parameters[xmlid] = self

    def product(self):
        return self.xmlid

    def __iter__(self):
        return [v for v in self.__dict__.values() if type(v) is AMDAComponentIndex].__iter__()

    def __contains__(self, item):
        item = to_xmlid(item)
        for comp in self:
            if item == to_xmlid(comp):
                return True
        return False


class AMDADatasetIndex(AMDAIndex, DatasetIndex):  # lgtm [py/conflicting-attributes]
    parameters: SimpleNamespace

    def __init__(self, meta: Dict, is_public=True):
        xmlid = meta.pop('xmlid')
        name = meta.pop('name')
        DatasetIndex.__init__(self=self, name=name, provider="amda", meta=meta)
        AMDAIndex.__init__(self=self, xmlid=xmlid, is_public=is_public)
        flat_inventories.amda.datasets[xmlid] = self

    def __iter__(self):
        return [v for v in self.__dict__.values() if type(v) is AMDAParameterIndex].__iter__()

    def __contains__(self, item):
        item = to_xmlid(item)
        for param in self:
            if (item == to_xmlid(param)) or (item in param):
                return True
        return False
