import configparser
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

from speasy import config
from speasy.cli import main
from speasy.core.codecs import get_codec

__HERE__ = os.path.dirname(os.path.abspath(__file__))
_CDF = f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf"


def _run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(list(argv))
    return code, out.getvalue()


class _IsolatedConfig(unittest.TestCase):
    """Every test gets its own config.ini and environment, never the user's."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ini = os.path.join(self.dir, 'config.ini')
        env = {k: v for k, v in os.environ.items() if not k.startswith('SPEASY_')}
        patches = [mock.patch.object(config, '_config', configparser.ConfigParser()),
                   mock.patch.object(config, 'SPEASY_CONFIG_FILE', self.ini),
                   mock.patch.dict(os.environ, {**env, 'COLUMNS': '300'}, clear=True)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def ini_value(self, section, key):
        saved = configparser.ConfigParser()
        saved.read(self.ini)
        return saved[section][key]


class TestArchive(_IsolatedConfig):

    def write(self, split_rule):
        path = os.path.join(self.dir, 'mine.yaml')
        with open(path, 'w') as f:
            f.write(f"my_ds:\n  inventory_path: mylab/MAG\n  master_file: {_CDF}\n"
                    f"  split_rule: {split_rule}\n  url_pattern: {_CDF}\n")
        return path

    def test_validate_good_file_exits_zero_and_prints_the_tree(self):
        code, out = _run('archive', 'validate', self.write('regular'),
                         '--start', '2022-01-01T01', '--stop', '2022-01-01T02')
        self.assertEqual(code, 0)
        self.assertIn('✓ my_ds: fetched', out)

    def test_validate_bad_file_exits_one(self):
        code, out = _run('archive', 'validate', self.write('regulr'))
        self.assertEqual(code, 1)
        self.assertIn("split_rule is 'regulr'", out)

    def test_validate_checks_every_file(self):
        code, out = _run('archive', 'validate', self.write('regulr'), os.path.join(self.dir, 'nope.yaml'))
        self.assertEqual(code, 1)
        self.assertIn("split_rule is 'regulr'", out)
        self.assertIn("nope.yaml does not exist", out)

    def test_validate_refuses_start_without_stop(self):
        code, out = _run('archive', 'validate', self.write('regular'), '--start', '2022-01-01')
        self.assertNotEqual(code, 0)
        self.assertIn('--start and --stop go together', out)

    def test_dirs_lists_every_lookup_dir_and_whether_it_exists(self):
        config.archive.extra_inventory_lookup_dirs.set(f"{self.dir},/nope/typo")
        code, out = _run('archive', 'dirs')
        self.assertEqual(code, 0)
        self.assertRegex(out, rf"{self.dir}.*yes")
        self.assertRegex(out, r"/nope/typo.*no")


class TestConfig(_IsolatedConfig):

    def test_show_lists_entries_with_their_source(self):
        config.proxy.url.set("https://example.org/cache")
        os.environ['SPEASY_CACHE_PATH'] = '/tmp/x'
        code, out = _run('config', 'show')
        self.assertEqual(code, 0)
        self.assertRegex(out, r"proxy\.url.*https://example\.org/cache.*file")
        self.assertRegex(out, r"cache\.path.*/tmp/x.*env")
        self.assertRegex(out, r"proxy\.enabled.*True.*default")

    def test_show_masks_passwords(self):
        config.amda.password.set("hunter2")
        code, out = _run('config', 'show', 'amda')
        self.assertNotIn("hunter2", out)
        self.assertNotIn("proxy.url", out)

    def test_set_writes_the_config_file(self):
        code, _ = _run('config', 'set', 'proxy.url', 'https://example.org/cache')
        self.assertEqual(code, 0)
        self.assertEqual(self.ini_value('PROXY', 'url'), 'https://example.org/cache')

    def test_set_warns_when_the_environment_overrides_it(self):
        os.environ['SPEASY_PROXY_URL'] = 'https://env.org'
        _, out = _run('config', 'set', 'proxy.url', 'https://example.org/cache')
        self.assertIn('SPEASY_PROXY_URL', out)

    def test_unknown_entry_suggests_the_close_one(self):
        code, out = _run('config', 'set', 'proxy.ulr', 'x')
        self.assertEqual(code, 1)
        self.assertIn("did you mean proxy.url?", out)

    def test_reset_removes_the_entry_from_the_file(self):
        config.proxy.url.set("https://example.org/cache")
        _run('config', 'reset', 'proxy.url')
        self.assertEqual(config.proxy.url.get(), config.proxy.url.default)

    def test_add_and_remove_directories(self):
        _run('config', 'add', 'archive.extra_inventory_lookup_dirs', self.dir, '~/b')
        self.assertEqual(config.archive.extra_inventory_lookup_dirs.get(),
                         {self.dir, os.path.expanduser('~/b')})
        _run('config', 'remove', 'archive.extra_inventory_lookup_dirs', '~/b')
        self.assertEqual(config.archive.extra_inventory_lookup_dirs.get(), {self.dir})

    def test_relative_directories_are_stored_absolute(self):
        with mock.patch('os.getcwd', return_value=self.dir):
            _run('config', 'add', 'core.user_codecs_extra_dirs', 'codecs')
        self.assertEqual(config.core.user_codecs_extra_dirs.get(), {os.path.join(self.dir, 'codecs')})

    def test_add_refuses_entries_that_are_not_lists(self):
        code, out = _run('config', 'add', 'proxy.url', 'x')
        self.assertEqual(code, 1)
        self.assertIn("proxy.url is not a list", out)


class TestProviders(_IsolatedConfig):

    def test_disable_then_enable(self):
        code, _ = _run('providers', 'disable', 'amda')
        self.assertEqual(code, 0)
        self.assertEqual(config.core.disabled_providers.get(), {'amda'})
        _run('providers', 'enable', 'amda')
        self.assertEqual(config.core.disabled_providers.get(), set())

    def test_enable_removes_every_alias(self):
        config.core.disabled_providers.set('cdaweb,csa')
        _run('providers', 'enable', 'cda')
        self.assertEqual(config.core.disabled_providers.get(), {'csa'})

    def test_unknown_provider_is_refused(self):
        code, out = _run('providers', 'disable', 'amdaa')
        self.assertEqual(code, 1)
        self.assertIn("unknown provider 'amdaa'", out)
        self.assertEqual(config.core.disabled_providers.get(), set())

    def test_list_shows_enabled_status_and_aliases(self):
        config.core.disabled_providers.set('csa')
        code, out = _run('providers', 'list')
        self.assertEqual(code, 0)
        self.assertRegex(out, r"csa.*no")
        self.assertRegex(out, r"cda.*yes.*cdaweb")


class TestGet(_IsolatedConfig):

    def setUp(self):
        super().setUp()
        self.var = get_codec('cdf').load_variable(file=_CDF, variable='BGSEc')
        p = mock.patch('speasy.get_data', return_value=self.var)
        self.get_data = p.start()
        self.addCleanup(p.stop)

    def test_prints_a_summary(self):
        code, out = _run('get', 'archive/x/BGSEc', '2022-01-01', '2022-01-02')
        self.assertEqual(code, 0)
        self.get_data.assert_called_once_with('archive/x/BGSEc', '2022-01-01', '2022-01-02')
        self.assertIn('BGSEc', out)
        self.assertIn('2022-01-01', out)

    def test_saves_to_cdf(self):
        target = os.path.join(self.dir, 'out.cdf')
        code, _ = _run('get', 'archive/x/BGSEc', '2022-01-01', '2022-01-02', '--output', target)
        self.assertEqual(code, 0)
        self.assertIsNotNone(get_codec('cdf').load_variable(file=target, variable='BGSEc'))

    def test_saves_to_csv(self):
        target = os.path.join(self.dir, 'out.csv')
        _run('get', 'archive/x/BGSEc', '2022-01-01', '2022-01-02', '--output', target)
        with open(target) as f:
            self.assertIn('2022-01-01', f.read())

    def test_unsupported_output_format_lists_the_supported_ones(self):
        code, out = _run('get', 'archive/x/BGSEc', '2022-01-01', '2022-01-02', '--output', 'x.xlsx')
        self.assertEqual(code, 1)
        self.assertRegex(out, r"\.xlsx.*\.cdf.*\.csv")

    def test_no_data_exits_one(self):
        self.get_data.return_value = None
        code, out = _run('get', 'archive/x/BGSEc', '2022-01-01', '2022-01-02')
        self.assertEqual(code, 1)
        self.assertIn('no data', out)


class TestCache(_IsolatedConfig):

    def test_info_shows_path_size_and_entries(self):
        code, out = _run('cache', 'info')
        self.assertEqual(code, 0)
        for word in ('path', 'size', 'entries'):
            self.assertIn(word, out.lower())


class TestCacheWarm(_IsolatedConfig):

    def setUp(self):
        super().setUp()
        var = get_codec('cdf').load_variable(file=_CDF, variable='BGSEc')
        p = mock.patch('speasy.get_data', return_value=var)
        self.get_data = p.start()
        self.addCleanup(p.stop)

    def test_fetches_every_product_on_every_range(self):
        code, out = _run('cache', 'warm', 'amda/a', 'amda/b',
                         '--range', '2018-01-01', '2018-01-02', '--range', '2019-01-01', '2019-01-02')
        self.assertEqual(code, 0)
        self.assertEqual([c.args for c in self.get_data.call_args_list],
                         [('amda/a', '2018-01-01', '2018-01-02'), ('amda/a', '2019-01-01', '2019-01-02'),
                          ('amda/b', '2018-01-01', '2018-01-02'), ('amda/b', '2019-01-01', '2019-01-02')])
        self.assertIn('4/4', out)

    def test_reads_ranges_from_a_file(self):
        ranges = os.path.join(self.dir, 'ranges.txt')
        with open(ranges, 'w') as f:
            f.write("# storm season\n2018-01-01 2018-01-02\n\n2019-01-01,2019-01-02\n")
        _run('cache', 'warm', 'amda/a', '--ranges-file', ranges)
        self.assertEqual([c.args for c in self.get_data.call_args_list],
                         [('amda/a', '2018-01-01', '2018-01-02'), ('amda/a', '2019-01-01', '2019-01-02')])

    def test_malformed_ranges_file_line_is_reported(self):
        ranges = os.path.join(self.dir, 'ranges.txt')
        with open(ranges, 'w') as f:
            f.write("2018-01-01 2018-01-02\n2019-01-01\n")
        code, out = _run('cache', 'warm', 'amda/a', '--ranges-file', ranges)
        self.assertEqual(code, 1)
        self.assertIn("ranges.txt line 2", out)
        self.get_data.assert_not_called()

    def test_a_failure_does_not_stop_the_others(self):
        self.get_data.side_effect = [RuntimeError("server down"), self.get_data.return_value]
        code, out = _run('cache', 'warm', 'amda/a', 'amda/b', '--range', '2018-01-01', '2018-01-02')
        self.assertEqual(code, 1)
        self.assertEqual(self.get_data.call_count, 2)
        self.assertIn('server down', out)
        self.assertIn('1/2', out)

    def test_workers_fetch_everything_too(self):
        code, out = _run('cache', 'warm', 'amda/a', 'amda/b', '--workers', '4',
                         '--range', '2018-01-01', '2018-01-02', '--range', '2019-01-01', '2019-01-02')
        self.assertEqual(code, 0)
        self.assertEqual(sorted(c.args for c in self.get_data.call_args_list),
                         [('amda/a', '2018-01-01', '2018-01-02'), ('amda/a', '2019-01-01', '2019-01-02'),
                          ('amda/b', '2018-01-01', '2018-01-02'), ('amda/b', '2019-01-01', '2019-01-02')])
        self.assertIn('4/4', out)

    def test_needs_at_least_one_worker(self):
        code, out = _run('cache', 'warm', 'amda/a', '--workers', '0', '--range', '2018-01-01', '2018-01-02')
        self.assertEqual(code, 1)
        self.assertIn('--workers', out)

    def test_needs_a_time_range(self):
        code, out = _run('cache', 'warm', 'amda/a')
        self.assertEqual(code, 1)
        self.assertIn('--range', out)


class TestHelp(unittest.TestCase):

    def test_no_command_lists_the_groups(self):
        code, out = _run()
        self.assertEqual(code, 0)
        for group in ('archive', 'config', 'providers', 'get', 'cache'):
            self.assertIn(group, out)


if __name__ == '__main__':
    unittest.main()
