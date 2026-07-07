import os
import tempfile
import unittest

import yaml

__HERE__ = os.path.dirname(os.path.abspath(__file__))

from speasy.core.cdf.inventory_extractor import make_dataset_index, extract_from_master
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

_VARIABLES_WITH_META_YAML = """\
my_dataset_meta:
  inventory_path: cda/test
  meta:
    Mission_group: ERG
    Data_type: l3
  variables:
    Bgse:
      meta:
        UNITS: nT
        CATDESC: B in GSE frame
    Bgsm:
      meta:
        UNITS: nT
        CATDESC: B in GSM frame
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


_REMOTE_MASTER_CDF_FILE = (
    "https://cdaweb.gsfc.nasa.gov/pub/data/ace/mag/level_2_cdaweb/mfi_k2/2022/"
    "ac_k2_mfi_20220101_v03.cdf"
)

_MASTER_FILE_CDF_REMOTE_YAML = f"""\
ac_mfi_cdf_remote_dataset:
  inventory_path: cda/test
  master_file: {_REMOTE_MASTER_CDF_FILE}
  codec: cdf
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.cdf
"""


_LOCAL_ERG_CDF = f"{__HERE__}/resources/erg_pwe_hfa_l3_1min_00000000_v01.cdf"
_LOCAL_ERG_SKELETON_YAML = f"{__HERE__}/resources/erg_pwe_hfa_l3_1min_00000000_v01.skeleton.yaml"


def _make_root():
    return SpeasyIndex(name='archive', provider='archive', uid='')


def _load_yaml_doc(yaml_doc):
    root = _make_root()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_doc)
        fname = f.name
    try:
        load_inventory_file(fname, root)
    finally:
        os.unlink(fname)
    return root


def _cdas_netcdf_url(dataset, variables, start, stop):
    # ask the CDAS REST service to generate a NetCDF export and return its (ephemeral) URL
    from speasy.core import http
    url = (f"https://cdaweb.gsfc.nasa.gov/WS/cdasr/1/dataviews/sp_phys/datasets/"
           f"{dataset}/data/{start},{stop}/{variables}?format=nc")
    resp = http.get(url, headers={"Accept": "application/json"})
    return resp.json()['FileDescription'][0]['Name']


def _public_meta(node):
    # meta of a node, without internal __spz_ keys and the archive config blob
    return {k: v for k, v in node.__dict__.items()
            if not k.startswith('__spz_') and not hasattr(v, 'spz_name') and k != 'spz_ga_cfg'}


def _variables_meta(dataset):
    return {v.spz_name(): _public_meta(v)
            for v in dataset.__dict__.values() if hasattr(v, 'spz_name')}


def _norm(obj):
    # YAML serialization turns tuples into lists; normalize so comparisons ignore that
    if isinstance(obj, (list, tuple)):
        return [_norm(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _norm(v) for k, v in obj.items()}
    return obj


def _scalar(value):
    # cdfpp skeleton stores every attribute value as a list;
    #  unwrap single-element lists [kHz] -> kHz for comparison with the CDF inventory
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return value[0]
    return value


def _inventory_to_inline_yaml(name, inventory_path, dataset, **archive_keys):
    doc = {name: {"inventory_path": inventory_path, **archive_keys,
                  "meta": _public_meta(dataset),
                  "variables": {var: {"meta": meta}
                                for var, meta in _variables_meta(dataset).items()}}}
    return yaml.safe_dump(doc, sort_keys=False)


class TestMakeDatasetIndex(unittest.TestCase):

    def test_returns_dataset_index_from_cdf_url(self):
        result = extract_from_master(
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

    def test_skips_dataset_with_variables_list(self):
        # the bare list-of-names format is no longer supported (no meta): dataset must be skipped
        root = _load_yaml_doc(_VARIABLES_YAML)
        test_node = root.__dict__['cda'].__dict__['test']
        self.assertNotIn('my_dataset', test_node.__dict__)

    def test_loads_dataset_with_variables_and_meta(self):
        # inline format: dataset-level meta + variables given as a dict with per-variable meta
        root = _load_yaml_doc(_VARIABLES_WITH_META_YAML)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('my_dataset_meta')
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)
        self.assertEqual(dataset.__dict__.get('Mission_group'), 'ERG')   # dataset-level meta
        bgse = dataset.__dict__['Bgse']
        self.assertEqual(bgse.__dict__.get('UNITS'), 'nT')               # variable-level meta
        self.assertEqual(bgse.__dict__.get('CATDESC'), 'B in GSE frame')
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
        # nc inventory is now rich (same pyistp path as cdf): variables carry their meta
        bgse = dataset.__dict__['BGSEc']
        self.assertEqual(bgse.__dict__.get('UNITS'), 'nT')
        self.assertIn('CATDESC', bgse.__dict__)

    def test_roundtrip_nc_master_to_inline_yaml(self):
        # nc master -> inventory A ; dump A as inline yaml ; reload -> inventory B ; A == B
        root_a = _load_yaml_doc(_MASTER_FILE_NC_YAML)
        ds_a = root_a.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_nc_dataset')
        self.assertIsNotNone(ds_a)

        inline_doc = _inventory_to_inline_yaml(
            'ac_mfi_nc_dataset', 'cda/test', ds_a,
            split_rule='regular', url_pattern='https://example.org/{Y}/data.nc')
        root_b = _load_yaml_doc(inline_doc)
        ds_b = root_b.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_nc_dataset')
        self.assertIsNotNone(ds_b)

        # same variables and same meta, modulo YAML's tuple->list (e.g. spz_shape)
        self.assertEqual(_norm(_variables_meta(ds_a)), _norm(_variables_meta(ds_b)))
        self.assertEqual(_norm(_public_meta(ds_a)), _norm(_public_meta(ds_b)))

    def test_roundtrip_cdf_master_to_inline_yaml(self):
        # cdf master -> inventory A ; dump A as inline yaml ; reload -> inventory B ; A == B
        root_a = _load_yaml_doc(_MASTER_FILE_CDF_YAML)
        ds_a = root_a.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_cdf_dataset')
        self.assertIsNotNone(ds_a)

        inline_doc = _inventory_to_inline_yaml(
            'ac_mfi_cdf_dataset', 'cda/test', ds_a,
            split_rule='regular', url_pattern='https://example.org/{Y}/data.cdf')
        root_b = _load_yaml_doc(inline_doc)
        ds_b = root_b.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_cdf_dataset')
        self.assertIsNotNone(ds_b)

        # same variables and same meta, modulo YAML's tuple->list (e.g. spz_shape)
        self.assertEqual(_norm(_variables_meta(ds_a)), _norm(_variables_meta(ds_b)))
        self.assertEqual(_norm(_public_meta(ds_a)), _norm(_public_meta(ds_b)))

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

    def test_loads_dataset_with_remote_master_file_cdf(self):
        # cdf master fetched from a remote CDAWeb /pub/ URL
        root = _load_yaml_doc(_MASTER_FILE_CDF_REMOTE_YAML)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_cdf_remote_dataset')
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)
        var_names = {v.spz_name() for v in dataset.__dict__.values() if hasattr(v, 'spz_name')}
        self.assertIn('Magnitude', var_names)
        self.assertIn('BGSEc', var_names)

    def test_loads_dataset_with_remote_master_file_nc(self):
        # nc master fetched from a remote URL generated on demand by the CDAS REST service
        nc_url = _cdas_netcdf_url("AC_H2_MFI", "Magnitude,BGSEc",
                                  "20090601T000000Z", "20090603T000000Z")
        yaml_doc = f"""\
ac_mfi_nc_remote_dataset:
  inventory_path: cda/test
  master_file: {nc_url}
  codec: nc
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.nc
"""
        root = _load_yaml_doc(yaml_doc)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_nc_remote_dataset')
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


class TestCdfYamlSameInventory(unittest.TestCase):
    # A master CDF and the YAML skeleton must describe the same inventory.

    def test_cdf_and_yaml_describe_same_inventory(self):
        # inventory A: local master CDF -> speasy inventory (filtered, scalar meta)
        parameters, dataset_meta = extract_from_master(
            _LOCAL_ERG_CDF, provider='archive', disable_cache=True)
        ds_a = make_dataset_index(name='erg_pwe_hfa_l3_1min', provider='archive',
                                  uid='archive/cda/test/erg_pwe_hfa_l3_1min',
                                  parameters=parameters, meta=dataset_meta)

        # inventory B: skeleton YAML -> speasy inventory.
        #  The cdfpp dump omits the archive plumbing key, so inject a minimal
        #  inventory_path 
        with open(_LOCAL_ERG_SKELETON_YAML) as f:
            doc = yaml.safe_load(f)
        for entry in doc.values():
            entry['inventory_path'] = 'cda/test'
        root_b = _load_yaml_doc(yaml.safe_dump(doc, sort_keys=False))
        ds_b = root_b.__dict__['cda'].__dict__['test'].__dict__.get('erg_pwe_hfa_l3_1min')
        self.assertIsNotNone(ds_b)

        vm_a = _variables_meta(ds_a)
        vm_b = _variables_meta(ds_b)

        # same variables: every data variable speasy extracts from the CDF appears in the YAML
        # (the cdfpp dump additionally lists support_data variables).
        self.assertGreater(len(vm_a), 0)
        self.assertTrue(set(vm_a).issubset(set(vm_b)),
                        f"CDF variables {set(vm_a)} not all present in YAML {set(vm_b)}")

        # expected metadata present and consistent, modulo cdfpp's list wrapping (D4)
        for var in ('Fuhr', 'ne_mgf'):
            self.assertIn(var, vm_a)
            self.assertIn('CATDESC', vm_a[var])
            self.assertIn('UNITS', vm_a[var])
            self.assertEqual(_scalar(vm_b[var].get('UNITS')), vm_a[var]['UNITS'])
        self.assertEqual(vm_a['Fuhr']['UNITS'], 'kHz')
        self.assertEqual(vm_a['ne_mgf']['UNITS'], '/cc')


if __name__ == '__main__':
    unittest.main()
