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


class FlatInventories:
    def __init__(self):
        pass
