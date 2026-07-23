import os
import tempfile
import unittest

import numpy as np
import yaml

__HERE__ = os.path.dirname(os.path.abspath(__file__))

from speasy.core.cdf.inventory_extractor import make_dataset_index, extract_from_master
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.codecs.codecs_registry import register_codec
from speasy.core.inventory.indexes import SpeasyIndex, DatasetIndex
from speasy.data_providers.generic_archive import load_inventory_file
from speasy.products import DataContainer, SpeasyVariable, VariableTimeAxis


@register_codec
class _MasterFileMetaTestCodec(CodecInterface):
    """A minimal non-ISTP codec that implements list_variables, used only to reproduce/guard
    against _dataset_from_master()'s non-ISTP branch building ParameterIndex objects without
    entry_meta (which carries spz_ga_cfg -- get_data() needs it to know how to fetch)."""

    def list_variables(self, file):
        return ['foo']

    def load_variables(self, variables, file, cache_remote_files=True, **kwargs):
        time = np.array(['2020-01-01'], dtype='datetime64[ns]')
        var = SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                             values=DataContainer(values=np.array([1.0])))
        return {v: var for v in variables}

    def load_variable(self, variable, file, cache_remote_files=True, **kwargs):
        return self.load_variables([variable], file, cache_remote_files, **kwargs).get(variable)

    def save_variables(self, variables, file=None, **kwargs):
        raise NotImplementedError

    @property
    def supported_extensions(self):
        return []

    @property
    def supported_mimetypes(self):
        return []

    @property
    def name(self):
        return "test_master_file_meta_codec"

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

_VARIABLES_WITH_UNKNOWN_CODEC_YAML = """\
bogus_codec_dataset:
  inventory_path: cda/test
  meta:
    Mission_group: ERG
  variables:
    Bgse:
      meta:
        UNITS: nT
  codec: not_a_real_codec
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

_MASTER_FILE_CDF_WITH_META_YAML = f"""\
ac_mfi_meta_override:
  inventory_path: cda/test
  master_file: {__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf
  codec: cdf
  meta:
    Custom_field: custom_value
    Data_type: yaml_override
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

# every registry key resolving to the same ISTP codec: extension(s), mime type(s) and class name.
# The docs present them as interchangeable, let them all yield the same inventory.
_ISTP_CODEC_SPELLINGS = {
    f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf": (
        'cdf', 'application/x-cdf', 'IstpCdf'),
    f"{__HERE__}/resources/ac_h2s_mfi_cdaweb.nc": (
        'nc', 'nc4', 'application/x-netcdf', 'application/netcdf', 'IstpNetCDF'),
}

# hapi/csv is a registered, non-ISTP codec that does not override list_variables, so it raises
# NotImplementedError (see test_codecs.py). The master file is never actually read here, it only
# has to exist.
_NO_LIST_VARIABLES_CODEC_YAML = f"""\
hapi_dataset:
  inventory_path: cda/test
  master_file: {__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf
  codec: hapi/csv
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.csv
"""

# a malformed entry (no inventory_path -> KeyError) placed before a perfectly valid one, in the
# same file. yaml preserves document order, so the valid entry is only reached if the bad one
# does not abort the loop.
_BAD_ENTRY_THEN_GOOD_YAML = f"""\
bad_dataset_no_inventory_path:
  master_file: {__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf
  codec: cdf
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.cdf

good_dataset:
  inventory_path: cda/test
  master_file: {__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf
  codec: cdf
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data.cdf
"""


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


def _dataset_from_codec_spelling(master_file, codec):
    """Build a test yaml doc with a given master file and codec"""
    yaml_doc = f"""\
spelled_dataset:
  inventory_path: cda/test
  master_file: {master_file}
  codec: {codec}
  split_rule: regular
  url_pattern: https://example.org/{{Y}}/data
"""
    root = _load_yaml_doc(yaml_doc)
    return root.__dict__['cda'].__dict__['test'].__dict__.get('spelled_dataset')


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

    def test_variable_from_inline_yaml_carries_archive_cfg_for_get_data(self):
        # GenericArchive._get_data() reads spz_ga_cfg off the ParameterIndex, not the DatasetIndex
        root = _load_yaml_doc(_VARIABLES_WITH_META_YAML)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('my_dataset_meta')
        bgse = dataset.__dict__['Bgse']
        ga_cfg = getattr(bgse, 'spz_ga_cfg', None)
        self.assertIsNotNone(ga_cfg)
        self.assertEqual(ga_cfg.get('url_pattern'), 'https://example.org/{Y}/data.cdf')
        self.assertEqual(ga_cfg.get('split_rule'), 'regular')

    def test_skips_inline_variables_dataset_with_unknown_codec(self):
        # unlike master_file entries, inline 'variables:' entries never validated 'codec' at all:
        # a typo would sail through inventory building and only blow up deep inside get_data(),
        # instead of being skipped up front like an unknown codec on the master_file path.
        root = _load_yaml_doc(_VARIABLES_WITH_UNKNOWN_CODEC_YAML)
        test_node = root.__dict__['cda'].__dict__['test']
        self.assertNotIn('bogus_codec_dataset', test_node.__dict__)

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

    def test_master_file_dataset_meta_fills_gaps_by_default(self):
        # meta on a master_file entry was completely ignored before the fix: Custom_field
        # (which the master doesn't have) never made it onto the dataset, and there was no way
        # to tell -- the master's own Data_type kept its real value either way. This test fails
        # on the Custom_field assertion before the fix.
        root = _load_yaml_doc(_MASTER_FILE_CDF_WITH_META_YAML)
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_meta_override')
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.__dict__.get('Custom_field'), 'custom_value')
        self.assertEqual(dataset.__dict__.get('Data_type'), 'K2>1-Hr Key Parameter Data')

    def test_master_file_dataset_meta_priority_yaml_overrides_master(self):
        root = _load_yaml_doc(_MASTER_FILE_CDF_WITH_META_YAML.replace(
            "codec: cdf", "codec: cdf\n  meta_priority: yaml"))
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('ac_mfi_meta_override')
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.__dict__.get('Custom_field'), 'custom_value')
        self.assertEqual(dataset.__dict__.get('Data_type'), 'yaml_override')

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

    def test_istp_codec_spellings_give_same_inventory(self):
        # ISTP codec may be specified an by extension, MIME type, or class name.
        # Any of those "names" should all return the same code path with
        # complete metadata.
        for master_file, spellings in _ISTP_CODEC_SPELLINGS.items():
            canonical, *aliases = spellings
            reference = _dataset_from_codec_spelling(master_file, canonical)
            self.assertIsNotNone(reference)
            # guard: the reference really is rich, so equality below cannot pass vacuously
            self.assertTrue(any(_variables_meta(reference).values()))
            for alias in aliases:
                with self.subTest(master=os.path.basename(master_file), codec=alias):
                    dataset = _dataset_from_codec_spelling(master_file, alias)
                    self.assertIsNotNone(dataset)
                    self.assertEqual(_norm(_variables_meta(dataset)),
                                     _norm(_variables_meta(reference)))
                    self.assertEqual(_norm(_public_meta(dataset)),
                                     _norm(_public_meta(reference)))

    def test_skips_dataset_whose_codec_cannot_list_variables(self):
        # hapi/csv is registered, so it gets past the "unknown codec" guard, but neither it nor its
        # base class overrides CodecInterface.list_variables, so calling it raises
        # NotImplementedError, which would escape load_inventory_file and build_inventory and end
        # up disabling the whole archive provider. Skip the dataset instead, like an unknown codec
        # already does.
        root = _load_yaml_doc(_NO_LIST_VARIABLES_CODEC_YAML)  # must not raise
        test_node = root.__dict__['cda'].__dict__['test']
        self.assertNotIn('hapi_dataset', test_node.__dict__)

    def test_get_data_works_for_master_file_with_non_istp_codec(self):
        # _dataset_from_master()'s non-ISTP branch (codec.list_variables(master_file)) built
        # ParameterIndex objects without entry_meta, so the dataset looked fine in the inventory
        # but get_data() crashed with AttributeError: 'ParameterIndex' object has no attribute
        # 'spz_ga_cfg' -- entry_meta is where spz_ga_cfg lives. This test fails before the fix.
        from speasy.data_providers.generic_archive import GenericArchive

        master_meta_yaml = f"""\
master_meta_dataset:
  inventory_path: cda/test
  master_file: {__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf
  codec: test_master_file_meta_codec
  split_rule: regular
  split_frequency: none
  url_pattern: {__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf
"""
        root = _load_yaml_doc(master_meta_yaml)
        param = root.__dict__['cda'].__dict__['test'].__dict__['master_meta_dataset'].__dict__['foo']

        provider = object.__new__(GenericArchive)
        result = provider._get_data(product=param, start_time="2020-01-01", stop_time="2020-01-02")

        self.assertIsNotNone(result)

    def test_bad_entry_does_not_drop_the_rest_of_the_file(self):
        # load_inventory_file loops over the entries with no guard, so the KeyError raised by the
        # first, malformed entry escapes: the valid entry that follows is never built, the
        # remaining yaml files are never read, and _safe_init_provider ends up disabling the whole
        # archive provider. A bad entry must cost only itself.
        root = _load_yaml_doc(_BAD_ENTRY_THEN_GOOD_YAML)  # must not raise
        dataset = root.__dict__['cda'].__dict__['test'].__dict__.get('good_dataset')
        self.assertIsNotNone(dataset)
        self.assertIsInstance(dataset, DatasetIndex)

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
        with open(_LOCAL_ERG_SKELETON_YAML) as f:
            doc = yaml.safe_load(f)
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
