import unittest
from ddt import ddt, data, unpack

import speasy as spz
from speasy.core.inventory.indexes import from_dict, to_dict, SpeasyIndex
from speasy.core.dataprovider import DataProvider


def compare_inventories(inventory1: SpeasyIndex, inventory2: SpeasyIndex):
    if inventory1.spz_name() != inventory2.spz_name():
        print(f"Name mismatch: {inventory1.spz_name()} != {inventory2.spz_name()}")
        return False
    for key in inventory1.__dict__.keys():
        if key not in inventory2.__dict__:
            print(f"Key missing: {key}")
            return False
        value1 = inventory1.__dict__[key]
        value2 = inventory2.__dict__[key]
        if isinstance(value1, SpeasyIndex) and isinstance(value2, SpeasyIndex):
            if not compare_inventories(value1, value2):
                return False
        elif value1 != value2:
            print(f"Value mismatch: {value1} != {value2}")
            return False
    return True


@ddt
class FromDictAndToDictPreserveInventory(unittest.TestCase):

    def assertInventoryEqual(self, inventory1: SpeasyIndex, inventory2: SpeasyIndex):
        if inventory1.spz_name() != inventory2.spz_name():
            self.fail(f"Name mismatch: {inventory1.spz_name()} != {inventory2.spz_name()}")
        for key in inventory1.__dict__.keys():
            if key not in inventory2.__dict__:
                self.fail(f"Key missing: {key}")
            value1 = inventory1.__dict__[key]
            value2 = inventory2.__dict__[key]
            if isinstance(value1, SpeasyIndex) and isinstance(value2, SpeasyIndex):
                self.assertInventoryEqual(value1, value2)
            elif value1 != value2:
                self.fail(f"Value mismatch: {value1}({type(value1)}) != {value2}({type(value2)}) for key {key}")

    @data(
        (spz.amda,),
        (spz.cda,),
        (spz.ssc,),
        (spz.csa,),
    )
    @unpack
    def test_from_dict_and_to_dict_preserve_inventory(self, provider: DataProvider):
        inventory = provider._inventory(provider_name=provider.provider_name, disable_proxy=True)
        self.assertInventoryEqual(inventory, from_dict(to_dict(inventory, version=2), version=2))
