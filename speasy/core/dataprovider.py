from speasy.inventories import flat_inventories, tree
from speasy.core.inventory import ProviderInventory
from speasy.core.inventory.indexes import SpeasyIndex
from typing import List


class DataProvider:
    def __init__(self, provider_name: str, provider_alt_names: List or None = None):
        self.provider_name = provider_name
        self.provider_alt_names = provider_alt_names or []
        self.flat_inventory = ProviderInventory()
        flat_inventories.__dict__[provider_name] = self.flat_inventory
        tree.__dict__[provider_name] = SpeasyIndex(provider=provider_name, name=provider_name, uid=provider_name)
        self.build_inventory(tree.__dict__[provider_name])
        for alt_name in self.provider_alt_names:
            flat_inventories.__dict__[alt_name] = self.flat_inventory
