import os
import tempfile
import unittest

__HERE__ = os.path.dirname(os.path.abspath(__file__))

from speasy.core.cdf.inventory_extractor import make_dataset_index, extract_from_master_cdf
from speasy.core.inventory.indexes import SpeasyIndex, DatasetIndex
from speasy.data_providers.generic_archive import load_inventory_file

_REACHABLE_MASTER_CDF = (
    "https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/"
    "erg_pwe_hfa_l3_1min_00000000_v01.cdf"
)
_UNREACHABLE_MASTER_CDF = "https://does-not-exist.invalid/master.cdf"

_VALID_YAML = f"""\
erg_pwe_hfa_l3_1min:
  inventory_path: cda/test
  master_cdf: {_REACHABLE_MASTER_CDF}
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.cdf
"""

_UNREACHABLE_YAML = f"""\
bad_dataset:
  inventory_path: cda/test
  master_cdf: {_UNREACHABLE_MASTER_CDF}
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.cdf
"""

_VARIABLES_YAML = """\
my_dataset:
  inventory_path: cda/test
  variables: [Bgse, Bgsm]
  split_rule: regular
  url_pattern: https://example.org/{Y}/data.cdf
"""

_MASTER_FILE_NC_YAML = f"""\
ac_mfi_nc_dataset:
  inventory_path: cda/test
  master_file: {__HERE__}/resources/ac_h2s_mfi_cdaweb.nc
  codec: nc
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.nc
"""

_MASTER_FILE_CDF_YAML = f"""\
ac_mfi_cdf_dataset:
  inventory_path: cda/test
  master_file: {__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf
  codec: cdf
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.cdf
"""

_MASTER_CDF_LOCAL_YAML = f"""\
ac_mfi_local_master_cdf:
  inventory_path: cda/test
  master_cdf: {__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.cdf
"""


def _make_root():
    return SpeasyIndex(name='archive', provider='archive', uid='')


class TestMakeDatasetIndex(unittest.TestCase):

    def test_returns_dataset_index_from_cdf_url(self):
        result = extract_from_master_cdf(
            _REACHABLE_MASTER_CDF,
            provider="archive",
            disable_cache=True,
        )
        self.assertIsNotNone(result)
        parameters, dataset_meta = result
        self.assertGreater(len(parameters), 0)
        dataset = make_dataset_index(
            name="erg_pwe_hfa_l3_1min",
            provider="archive",
            uid="archive/cda/test/erg_pwe_hfa_l3_1min",
            parameters=parameters,
            meta=dataset_meta,
        )
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)
        built_parameters = [v for v in dataset.__dict__.values() if hasattr(v, 'spz_name')]
        self.assertGreater(len(built_parameters), 0)



class TestLoadInventoryFile(unittest.TestCase):

    def test_loads_dataset_with_master_cdf(self):
        root = _make_root()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(_VALID_YAML)
            fname = f.name
        try:
            load_inventory_file(fname, root)
        finally:
            os.unlink(fname)
        self.assertIn('cda', root.__dict__)
        self.assertIn('test', root.__dict__['cda'].__dict__)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('erg_pwe_hfa_l3_1min')
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)

    def test_loads_dataset_with_variables_key(self):
        root = _make_root()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(_VARIABLES_YAML)
            fname = f.name
        try:
            load_inventory_file(fname, root)
        finally:
            os.unlink(fname)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('my_dataset')
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)
        var_names = {v.spz_name() for v in dataset.__dict__.values() if hasattr(v, 'spz_name')}
        self.assertEqual(var_names, {'Bgse', 'Bgsm'})

    def test_loads_dataset_with_master_file_nc(self):
        root = _make_root()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(_MASTER_FILE_NC_YAML)
            fname = f.name
        try:
            load_inventory_file(fname, root)
        finally:
            os.unlink(fname)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_nc_dataset')
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)
        var_names = {v.spz_name() for v in dataset.__dict__.values() if hasattr(v, 'spz_name')}
        self.assertIn('Magnitude', var_names)
        self.assertIn('BGSEc', var_names)

    def test_loads_dataset_with_master_file_cdf(self):
        root = _make_root()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(_MASTER_FILE_CDF_YAML)
            fname = f.name
        try:
            load_inventory_file(fname, root)
        finally:
            os.unlink(fname)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_cdf_dataset')
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)
        var_names = {v.spz_name() for v in dataset.__dict__.values() if hasattr(v, 'spz_name')}
        self.assertIn('Magnitude', var_names)
        self.assertIn('BGSEc', var_names)

    def test_loads_dataset_with_local_master_cdf_no_codec(self):
        # master_cdf key without codec + local file: must route through the cdf path
        # (mirrors the 14 datasets of cda.yaml, without network dependency)
        root = _make_root()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(_MASTER_CDF_LOCAL_YAML)
            fname = f.name
        try:
            load_inventory_file(fname, root)
        finally:
            os.unlink(fname)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_local_master_cdf')
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)
        var_names = {v.spz_name() for v in dataset.__dict__.values() if hasattr(v, 'spz_name')}
        self.assertIn('Magnitude', var_names)
        self.assertIn('BGSEc', var_names)

    def test_skips_dataset_if_master_unreachable(self):
        root = _make_root()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(_UNREACHABLE_YAML)
            fname = f.name
        try:
            load_inventory_file(fname, root)
        finally:
            os.unlink(fname)
        self.assertNotIn('bad_dataset', root.__dict__.get('cda', SpeasyIndex(name='x', provider='x', uid='')).__dict__)


if __name__ == '__main__':
    unittest.main()
