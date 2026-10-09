import os
import subprocess
import sys
import unittest
from ddt import ddt, data

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

    # Names, not spz.<provider>: providers start on first access, and this list is evaluated at import.
    @data("amda", "cda", "ssc", "csa")
    def test_from_dict_and_to_dict_preserve_inventory(self, provider_name: str):
        provider: DataProvider = getattr(spz, provider_name)
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
        # this is the same code path build_inventory() takes on a fresh build.
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


def _master_dataset(name: str, mastercdf: str, start: str) -> DatasetIndex:
    return DatasetIndex(name=name, provider='cda', uid=name,
                        meta={'mastercdf': f'https://example.org/0MASTERS/{mastercdf}',
                              'start_date': start, 'stop_date': '2030-01-01T00:00:00Z',
                              'serviceprovider_ID': name})


class CdaUpdateTree(unittest.TestCase):
    def test_each_dataset_gets_parameters_from_its_own_master(self):
        datasets = {
            'ELA_L1_STATE_PRED': _master_dataset('ELA_L1_STATE_PRED', 'ela_l1_state_pred_00000000_v01.cdf',
                                                 '2018-01-01T00:00:00Z'),
            'ERG_HFA': _master_dataset('ERG_HFA', 'erg_pwe_hfa_l3_1min_00000000_v01.cdf', '2017-01-01T00:00:00Z'),
            'GE_H0_CPI': _master_dataset('GE_H0_CPI', 'ge_h0_cpi_00000000_v01.cdf', '1995-01-01T00:00:00Z'),
            'NO_MASTER': _master_dataset('NO_MASTER', 'does_not_exist_00000000_v01.cdf', '2000-01-01T00:00:00Z'),
        }
        root = SpeasyIndex(name='root', provider='cda', uid='root')
        root.__dict__.update(datasets)

        update_tree(root, master_cdf_dir=f"{__HERE__}/resources")

        for name, param_name in (('ELA_L1_STATE_PRED', 'ela_att_solution_date'), ('ERG_HFA', 'Fuhr'),
                                 ('GE_H0_CPI', 'SW_V')):
            dataset = datasets[name]
            param = dataset.__dict__.get(param_name)
            self.assertIsNotNone(param, f"{param_name} missing from {name}")
            self.assertEqual(param.spz_uid(), f"{name}/{param_name}")
            self.assertEqual(param.dataset, name)
            self.assertEqual(param.start_date, dataset.start_date)
        self.assertFalse(any(isinstance(v, SpeasyIndex) for v in datasets['NO_MASTER'].__dict__.values()))

    def test_parameters_record_their_time_axis(self):
        # Variables sharing a DEPEND_0 can be served on a single time column (HAPI datasets).
        dataset = _master_dataset('GE_H0_CPI', 'ge_h0_cpi_00000000_v01.cdf', '1995-01-01T00:00:00Z')
        root = SpeasyIndex(name='root', provider='cda', uid='root')
        root.__dict__['GE_H0_CPI'] = dataset

        update_tree(root, master_cdf_dir=f"{__HERE__}/resources")

        self.assertEqual(dataset.SW_V.DEPEND_0, 'Epoch')


# Replays the state of a CDA inventory build run by init_providers() during `import speasy`: the
# main thread holds the `speasy` import lock while update_tree() runs (SciQLop/speasy#381).
_UPDATE_TREE_DURING_SPEASY_IMPORT = """
import importlib._bootstrap, sys
sys.path.insert(0, sys.argv[1])
import speasy
from test_inventories import _master_dataset
from speasy.core.inventory.indexes import SpeasyIndex
from speasy.data_providers.cda._inventory_builder._cdf_masters_parser import update_tree
root = SpeasyIndex(name='root', provider='cda', uid='root')
root.__dict__['GE_H0_CPI'] = _master_dataset('GE_H0_CPI', 'ge_h0_cpi_00000000_v01.cdf', '1995-01-01T00:00:00Z')
speasy.__spec__._initializing = True
with importlib._bootstrap._ModuleLockManager('speasy'):
    update_tree(root, master_cdf_dir=sys.argv[1] + '/resources')
print(len(root.GE_H0_CPI.__dict__))
"""


class CdaUpdateTreeDuringImport(unittest.TestCase):
    def test_does_not_hang_while_speasy_is_importing(self):
        result = subprocess.run([sys.executable, "-c", _UPDATE_TREE_DURING_SPEASY_IMPORT, __HERE__],
                                env={**os.environ, "SPEASY_SKIP_INIT_PROVIDERS": "1"},
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
