from collections.abc import Callable

from .indexes import (
    CatalogIndex,
    ComponentIndex,
    DatasetIndex,
    ParameterIndex,
    SpeasyIndex,
    TemplatedParameterIndex,
    TimetableIndex,
)


class ProviderInventory:
    parameters: dict[str, ParameterIndex]
    datasets: dict[str, DatasetIndex]
    missions: dict[str, SpeasyIndex]
    timetables: dict[str, TimetableIndex]
    catalogs: dict[str, CatalogIndex]
    components: dict[str, ComponentIndex]

    _type_lookup: dict[type, Callable]

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
