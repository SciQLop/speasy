from typing import Dict, Callable
from .indexes import ParameterIndex, DatasetIndex, TimetableIndex, ComponentIndex, CatalogIndex, SpeasyIndex,TemplatedParameterIndex


class ProviderInventory:
    parameters: Dict[str, ParameterIndex]
    datasets: Dict[str, DatasetIndex]
    missions: Dict[str, SpeasyIndex]
    timetables: Dict[str, TimetableIndex]
    catalogs: Dict[str, CatalogIndex]
    components: Dict[str, ComponentIndex]

    _type_lookup: Dict[type, Callable]

    def __init__(self):
        self.parameters = {}
        self.datasets = {}
        self.instruments = {}
        self.observatories = {}
        self.missions = {}
        self.timetables = {}
        self.catalogs = {}
        self.components = {}
        self._type_lookup = {
            ParameterIndex: lambda node: self.parameters.__setitem__(node.spz_uid(), node),
            TemplatedParameterIndex: lambda node: self.parameters.__setitem__(node.spz_uid(), node),
            DatasetIndex: lambda node: self.datasets.__setitem__(node.spz_uid(), node),
            TimetableIndex: lambda node: self.timetables.__setitem__(node.spz_uid(), node),
            ComponentIndex: lambda node: self.components.__setitem__(node.spz_uid(), node),
            CatalogIndex: lambda node: self.catalogs.__setitem__(node.spz_uid(), node),
        }

    def clear(self):
        self.parameters.clear()
        self.datasets.clear()
        self.instruments.clear()
        self.observatories.clear()
        self.missions.clear()
        self.timetables.clear()
        self.catalogs.clear()
        self.components.clear()

    def _register_nodes(self, node: SpeasyIndex):
        if isinstance(node, SpeasyIndex):
            for child in node.__dict__.values():
                self._type_lookup.get(type(child), lambda _: None)(child)
                self._register_nodes(child)

    def update(self, root: SpeasyIndex):
        self._register_nodes(root)


class FlatInventories:
    def __init__(self):
        pass
