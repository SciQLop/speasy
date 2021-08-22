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
        self.missions = {}
        self.timetables = {}
        self.catalogs = {}
        self.components = {}


class FlatInventories:
    amda = ProviderInventory()
    ssc = ProviderInventory()


flat_inventories = FlatInventories()


def reset_amda_inventory():
    flat_inventories.amda = ProviderInventory()
