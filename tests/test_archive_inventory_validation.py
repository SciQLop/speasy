import contextlib
import io
import os
import shutil
import tempfile
import unittest
import unittest.mock

import numpy as np
import pycdfpp

from speasy.core.direct_archive_downloader import get_product
from speasy.core.inventory.indexes import SpeasyIndex
from speasy.data_providers.generic_archive import (GenericArchive, load_inventory_file, validate_inventory_file,
                                                   _read_entries, _entry_problems)

__HERE__ = os.path.dirname(os.path.abspath(__file__))
_CDF = f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf"
_LOG = 'speasy.data_providers.generic_archive'

_GOOD = f"""\
my_ds:
  inventory_path: mylab/MAG
  master_file: {_CDF}
  split_rule: regular
  url_pattern: {_CDF}
"""


def _entry(**fields):
    lines = '\n'.join(f"  {k}: {v}" for k, v in fields.items())
    return f"my_ds:\n{lines}\n"


def _good_entry(**overrides):
    fields = dict(inventory_path='mylab/MAG', master_file=_CDF, split_rule='regular', url_pattern=_CDF)
    fields.update(overrides)
    return _entry(**{k: v for k, v in fields.items() if v is not None})


class _TempYaml(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, content, name='mine.yaml'):
        path = os.path.join(self.dir, name)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def load(self, content):
        root = SpeasyIndex(name='archive', provider='archive', uid='')
        with self.assertLogs(_LOG, level='WARNING') as logs:
            load_inventory_file(self.write(content), root)
        return root, '\n'.join(logs.output)

    def assertNoDataset(self, root):
        self.assertNotIn('mylab', root.__dict__)

    def validate(self, content, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok = validate_inventory_file(self.write(content), *args)
        return ok, out.getvalue()

    def _non_istp_cdf(self):
        cdf = pycdfpp.CDF()
        cdf.add_variable("Epoch", values=np.arange("2022-01-01T00:00:00", "2022-01-01T00:00:10",
                                                   dtype="datetime64[s]").astype("datetime64[ns]"),
                         data_type=pycdfpp.DataType.CDF_TIME_TT2000)
        cdf.add_variable("B", values=np.ones((10, 3)))
        path = os.path.join(self.dir, 'plain.cdf')
        pycdfpp.save(cdf, path)
        return path


class TestBrokenFilesCostOnlyThemselves(_TempYaml):

    def test_yaml_syntax_error_is_reported_with_its_location(self):
        _, log = self.load(_GOOD + "  bad: [unclosed\n")
        self.assertRegex(log, r"mine\.yaml.*not valid YAML.*line \d+")

    def test_empty_file_is_reported(self):
        _, log = self.load("")
        self.assertRegex(log, r"mine\.yaml.*is empty")

    def test_top_level_list_is_reported(self):
        _, log = self.load(f"- inventory_path: mylab/MAG\n  master_file: {_CDF}\n")
        self.assertRegex(log, r"mine\.yaml.*must map dataset names to their description")

    def build_inventory(self, extra_dirs):
        root = SpeasyIndex(name='archive', provider='archive', uid='')
        empty = os.path.join(self.dir, 'empty')
        with unittest.mock.patch(f'{_LOG}.cfg.extra_inventory_lookup_dirs.get', return_value=set(extra_dirs)), \
                unittest.mock.patch(f'{_LOG}._global_inventory_dir', return_value=empty), \
                unittest.mock.patch(f'{_LOG}.user_inventory_dir', return_value=empty):
            object.__new__(GenericArchive).build_inventory(root)
        return root

    def test_unreadable_file_does_not_disable_the_provider(self):
        self.write("a: [unclosed\n", name='broken.yaml')
        self.write(_GOOD, name='good.yaml')
        with self.assertLogs(_LOG, level='WARNING'):
            root = self.build_inventory([self.dir])  # must not raise
        self.assertIn('my_ds', root.mylab.MAG.__dict__)

    def test_missing_lookup_dir_is_reported(self):
        missing = os.path.join(self.dir, 'typo')
        with self.assertLogs(_LOG, level='WARNING') as logs:
            self.build_inventory([missing])
        self.assertRegex('\n'.join(logs.output), rf"{missing} does not exist")


class TestEntryChecks(_TempYaml):

    def test_missing_required_key_skips_the_dataset(self):
        root, log = self.load(_good_entry(url_pattern=None))
        self.assertIn("my_ds: missing required key 'url_pattern'", log)
        self.assertNoDataset(root)

    def test_unknown_key_suggests_the_close_known_one(self):
        _, log = self.load(_good_entry(master_file=None, master_cfd=_CDF))
        self.assertIn("my_ds: unknown key 'master_cfd' (did you mean 'master_cdf'?)", log)

    def test_unknown_key_alone_does_not_skip_the_dataset(self):
        root, log = self.load(_good_entry(description='my data'))
        self.assertIn("unknown key 'description'", log)
        self.assertIn('my_ds', root.mylab.MAG.__dict__)

    def test_bad_split_rule_lists_the_allowed_values(self):
        root, log = self.load(_good_entry(split_rule='regulr'))
        self.assertIn("my_ds: split_rule is 'regulr', expected one of: regular, random", log)
        self.assertNoDataset(root)

    def test_bad_split_frequency_lists_the_allowed_values(self):
        root, log = self.load(_good_entry(split_frequency='weekly'))
        self.assertIn("my_ds: split_frequency is 'weekly', expected one of: daily, monthly, yearly, none", log)
        self.assertNoDataset(root)

    def test_random_split_needs_fname_regex(self):
        root, log = self.load(_good_entry(split_rule='random'))
        self.assertIn("my_ds: split_rule 'random' needs a 'fname_regex'", log)
        self.assertNoDataset(root)

    def test_no_variable_source_is_reported(self):
        root, log = self.load(_good_entry(master_file=None))
        self.assertIn("my_ds: needs 'master_file', 'master_cdf' or 'variables'", log)
        self.assertNoDataset(root)

    def test_entry_that_is_not_a_mapping_is_reported(self):
        root, log = self.load("my_ds: oops\n")
        self.assertIn("my_ds: expected a mapping of fields, got 'oops'", log)
        self.assertNoDataset(root)

    def test_failed_dataset_leaves_no_empty_folder(self):
        root, _ = self.load(_good_entry(master_file='/nope/missing.cdf'))
        self.assertNoDataset(root)

    def test_dataset_without_variables_is_skipped(self):
        plain = self._non_istp_cdf()
        root, log = self.load(_good_entry(master_file=plain, url_pattern=plain))
        self.assertIn("my_ds: no variables found", log)
        self.assertNoDataset(root)

    def test_bundled_inventories_pass_the_checks(self):
        for name in ('cda.yaml', 'themis_cdpp.yaml.example'):
            entries, problems = _read_entries(f"{__HERE__}/../speasy/data/archive/{name}")
            self.assertEqual(problems, [])
            self.assertEqual([p for n, e in entries.items() for kind in _entry_problems(n, e) for p in kind], [])


class TestGetProductSplitRule(unittest.TestCase):

    def test_unknown_split_rule_raises(self):
        with self.assertRaisesRegex(ValueError, r"split_rule 'regulr'.*regular, random"):
            get_product(url_pattern=_CDF, split_rule='regulr', variable='BGSEc',
                        start_time='2022-01-01', stop_time='2022-01-02')


class TestValidateInventoryFile(_TempYaml):

    def test_good_file_prints_the_inventory_tree(self):
        ok, out = self.validate(_GOOD, "2022-01-01T01", "2022-01-01T02")
        self.assertTrue(ok)
        self.assertRegex(out, r"✓ my_ds: fetched \w+ \(\d+ samples\)")
        for node in ('mylab', 'MAG', 'my_ds', 'BGSEc'):
            self.assertIn(node, out)

    def test_without_time_range_says_fetching_was_not_tested(self):
        ok, out = self.validate(_GOOD)
        self.assertTrue(ok)
        self.assertIn("start_time and stop_time", out)

    def test_bad_file_lists_every_problem_and_no_tree(self):
        ok, out = self.validate(_good_entry(split_rule='regulr', url_pattern=None))
        self.assertFalse(ok)
        self.assertIn("split_rule is 'regulr'", out)
        self.assertIn("missing required key 'url_pattern'", out)
        self.assertNotIn("Inventory:", out)

    def test_pyistp_complaints_are_attributed_to_the_dataset(self):
        plain = self._non_istp_cdf()
        ok, out = self.validate(_good_entry(master_file=plain, url_pattern=plain))
        self.assertFalse(ok)
        self.assertRegex(out, r"my_ds:.*Non compliant ISTP file")

    def test_fetch_failure_shows_the_expanded_url(self):
        missing = os.path.join(self.dir, "{Y}/x_{Y}{M:02d}{D:02d}.cdf")
        ok, out = self.validate(_good_entry(url_pattern=missing), "2022-01-01T01", "2022-01-01T02")
        self.assertFalse(ok)
        self.assertIn("x_20220101.cdf", out)

    def test_missing_file_is_reported(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok = validate_inventory_file(os.path.join(self.dir, 'nope.yaml'))
        self.assertFalse(ok)
        self.assertIn("nope.yaml does not exist", out.getvalue())


if __name__ == '__main__':
    unittest.main()
