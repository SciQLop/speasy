from types import SimpleNamespace
from speasy.core.inventory import ProviderInventory, FlatInventories

flat_inventories = FlatInventories()
tree = SimpleNamespace()
data_tree = tree


def reset_amda_inventory():
    flat_inventories.amda = ProviderInventory()
