import unittest
from datetime import datetime, timezone

from speasy.core.dataprovider import provider_class
from speasy.data_providers import ssc, cdpp3dview
from speasy.data_providers.cdpp3dview import Cdpp3dViewWebException

_TRANSPORT_OPTIONS = dict(extra_http_headers={'X': 'y'}, progress=True, disable_proxy=True, disable_cache=True,
                          prefer_cache=True, force_refresh=True, if_newer_than=datetime(2020, 1, 1), method='API',
                          debug=True, format='cdf')


class ProviderClass(unittest.TestCase):
    def test_aliases_give_the_main_provider_class(self):
        self.assertIs(provider_class('cdaweb'), provider_class('cda'))
        self.assertIs(provider_class('sscweb'), provider_class('ssc'))
        self.assertEqual(provider_class('3DView').NAME, 'cdpp3dview')

    def test_unknown_provider_says_which_ones_exist(self):
        with self.assertRaisesRegex(ValueError, r"Unknown provider 'nope'.*'amda'.*'cda'"):
            provider_class('nope')


class RequestOptions(unittest.TestCase):
    def test_providers_without_data_shaping_options_give_nothing(self):
        for name in ('cda', 'csa', 'hapi', 'uiowaephtool', 'archive'):
            with self.subTest(provider=name):
                self.assertEqual(provider_class(name).request_options(**_TRANSPORT_OPTIONS), {})

    def test_ssc_fills_its_default_and_ignores_case(self):
        options = provider_class('ssc').request_options
        self.assertEqual(options(), {'coordinate_system': 'gse'})
        self.assertEqual(options(coordinate_system='GSE', **_TRANSPORT_OPTIONS), options())
        self.assertEqual(options(coordinate_system='geo'), {'coordinate_system': 'geo'})

    def test_3dview_fills_its_defaults(self):
        self.assertEqual(provider_class('cdpp3dview').request_options(**_TRANSPORT_OPTIONS),
                         {'coordinate_frame': 'J2000', 'sampling': '600'})

    def test_3dview_coordinate_system_is_an_alias(self):
        options = provider_class('cdpp3dview').request_options
        self.assertEqual(options(coordinate_system='GSE'), options(coordinate_frame='GSE'))

    def test_3dview_conflicting_aliases_raise(self):
        options = provider_class('cdpp3dview').request_options
        with self.assertRaises(Cdpp3dViewWebException):
            options(coordinate_frame='GSE', coordinate_system='GSM')

    def test_3dview_sampling_as_number_or_string_is_the_same(self):
        options = provider_class('cdpp3dview').request_options
        self.assertEqual(options(sampling=60), options(sampling='60'))

    def test_amda_never_uses_a_config_default(self):
        # the request falls back on the AMDA.output_format config entry, which would make the same
        # call give different options on two machines
        self.assertEqual(provider_class('amda').request_options(**_TRANSPORT_OPTIONS), {'restricted_period': False})

    def test_amda_keeps_what_the_caller_passed(self):
        self.assertEqual(
            provider_class('amda').request_options(output_format='CSV', restricted_period=True,
                                                   product_inputs={'a': 1}),
            {'output_format': 'csv', 'restricted_period': True, 'product_inputs': {'a': 1}})


class CacheKeysUnchanged(unittest.TestCase):
    """The defaults moved to constants shared with request_options: cache keys must stay byte-identical, or every
    user's cache would miss once."""
    _START = datetime(2020, 1, 1, tzinfo=timezone.utc)

    def test_ssc(self):
        self.assertEqual(ssc._make_cache_entry_name('ssc_orbits', 'ace', '2020-01-01T00:00:00+00:00'),
                         'ssc_orbits/ace/gse/2020-01-01T00:00:00+00:00')
        self.assertEqual(ssc._make_cache_entry_name('ssc_orbits', 'ace', 'T', coordinate_system='GSE'),
                         'ssc_orbits/ace/GSE/T')
        self.assertEqual(ssc.get_parameter_args(self._START, self._START, 'ace')['coordinate_system'], 'gse')

    def test_3dview(self):
        self.assertEqual(cdpp3dview._make_cache_entry_name('cdpp3dview', 'p', 'T'), 'cdpp3dview/p/J2000/600/T')
        self.assertEqual(cdpp3dview._make_cache_entry_name('cdpp3dview', 'p', 'T', coordinate_frame='GSE', sampling=60),
                         'cdpp3dview/p/GSE/60/T')
        args = cdpp3dview.get_parameter_args(self._START, self._START, 'p')
        self.assertEqual((args['coordinate_system'], args['sampling']), ('J2000', '600'))


if __name__ == '__main__':
    unittest.main()
