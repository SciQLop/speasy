from typing import Dict


class ProviderInventory:
    parameters: Dict
    datasets: Dict
    missions: Dict
    timetables: Dict
    catalogs: Dict
    components: Dict

    def __init__(self):
        self.parameters = {}
        self.datasets = {}
        self.instruments = {}
        self.observatories = {}
        self.missions = {}
        self.timetables = {}
        self.catalogs = {}
        self.components = {}

    def clear(self):
        self.parameters.clear()
        self.datasets.clear()
        self.instruments.clear()
        self.observatories.clear()
        self.missions.clear()
        self.timetables.clear()
        self.catalogs.clear()
        self.components.clear()


class FlatInventories:
    def __init__(self):
        pass
