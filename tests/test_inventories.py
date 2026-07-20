import os
import unittest
from ddt import ddt, data, unpack

import speasy as spz
from speasy.core.inventory.indexes import from_dict, to_dict, SpeasyIndex, DatasetIndex
from speasy.core.dataprovider import DataProvider
from speasy.data_providers.cda._inventory_builder._cdf_masters_parser import update_tree

__HERE__ = os.path.dirname(os.path.abspath(__file__))


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

    def test_from_dict_and_to_dict_preserve_non_string_typed_attributes(self):
        # Reproduces a real CDAWeb master CDF whose FILLVAL is CDF_TIME_TT2000-typed (the ISTP
        # far-future fill sentinel): filter_variable_meta() stores whatever pycdfpp hands back
        # for that attribute with no type normalization, so the inventory ends up holding a raw
        # pycdfpp.tt2000_t object. to_dict()'s generic fallback stringifies it on the way out, but
        # from_dict() never converts it back -- so a freshly built inventory (which never went
        # through to_dict/from_dict) does not equal its own round-tripped copy.
        #
        # This goes through CDA's real update_tree(), offline, against a real master CDF checked
        # into tests/resources (no live CDAWeb catalog / no persisted inventory cache involved) --
        # this is the same code path load_master_cdf()/build_inventory() takes on a fresh build.
        dataset = DatasetIndex(name='ELA_L1_STATE_PRED', provider='cda', uid='ELA_L1_STATE_PRED',
                               meta={
                                   'mastercdf': 'ela_l1_state_pred_00000000_v01.cdf',
                                   'start_date': '2018-01-01T00:00:00Z',
                                   'stop_date': '2030-01-01T00:00:00Z',
                                   'serviceprovider_ID': 'ELA_L1_STATE_PRED',
                               })
        root = SpeasyIndex(name='root', provider='cda', uid='root')
        root.__dict__['ELA_L1_STATE_PRED'] = dataset

        update_tree(root, master_cdf_dir=f"{__HERE__}/resources")

        param = dataset.__dict__.get('ela_att_solution_date')
        self.assertIsNotNone(param)
        self.assertInventoryEqual(root, from_dict(to_dict(root, version=2), version=2))
