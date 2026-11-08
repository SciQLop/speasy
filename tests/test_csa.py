import io
import os
import sys
import tarfile
import unittest
from datetime import datetime
from types import SimpleNamespace

import numpy as np

import speasy as spz
from speasy.core.codecs import get_codec
from speasy.data_providers.csa import (_download_variable, _load_variable, cache_entry_name, delivery_format,
                                       get_parameter_args)

sys.path.insert(0, os.path.dirname(__file__))
from test_cef_codec import SCALAR  # noqa: E402


class CSAInventory(unittest.TestCase):
    def test_can_get_full_inventory_without_proxy(self):
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        spz.csa.update_inventory()
        os.environ.pop(spz.config.proxy.enabled.env_var_name)
        self.assertGreaterEqual(len(spz.inventories.flat_inventories.csa.parameters), 1932)
        self.assertIn('B_vec_xyz_gse__C1_CP_FGM_SPIN',
                      spz.inventories.tree.csa.Cluster.Cluster_1.FGM1.C1_CP_FGM_SPIN.__dict__)
        self.assertIn('C1_CP_AUX_LSTAR', spz.inventories.flat_inventories.csa.datasets)


_TAP_ROWS = {
    "v_mission": [{"name": "Cluster"}],
    "v_observatory": [{"name": n, "mission_name": "Cluster"} for n in ("Cluster-1", "Cluster-4", "MULTIPLE")],
    "v_instrument": [{"name": "RAPID4", "observatories": "Cluster-4"}, {"name": "PEACE4", "observatories": "Cluster-4"},
                     {"name": "AUX1", "observatories": "Cluster-1"}, {"name": "AUX4", "observatories": "Cluster-4"}],
    "v_dataset": [{"dataset_id": "C4_CP_BOTH", "instruments": "RAPID4, PEACE4", "end_date": "2020-01-01"},
                  {"dataset_id": "C4_CP_BOTH_AGAIN", "instruments": "PEACE4, RAPID4", "end_date": "2020-01-01"},
                  {"dataset_id": "CL_SP_AUX", "instruments": "AUX4, AUX1", "end_date": "2020-01-01"}],
    "v_parameter": [],
}


class CSADatasetsOfSeveralInstruments(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        from speasy.core.inventory.indexes import SpeasyIndex
        from speasy.data_providers.csa import build_inventory
        with patch("speasy.data_providers.csa.tap.query",
                   lambda url, query: _TAP_ROWS[query.split("csa.")[1].split()[0]]):
            self.cluster = build_inventory(SpeasyIndex("csa", "csa", "csa")).Cluster

    @staticmethod
    def group(node, *names):
        return next(child for key, child in node.__dict__.items() if all(name in key for name in names))

    def test_instruments_of_one_spacecraft_are_grouped_under_it(self):
        group = self.group(self.cluster.Cluster_4, "PEACE4", "RAPID4")
        self.assertIn("C4_CP_BOTH", group.__dict__)
        self.assertIn("C4_CP_BOTH_AGAIN", group.__dict__)

    def test_instruments_of_several_spacecraft_are_grouped_under_multiple(self):
        group = self.group(self.cluster.MULTIPLE, "AUX1", "AUX4")
        self.assertIn("CL_SP_AUX", group.__dict__)


class CSADeliveryFormat(unittest.TestCase):
    def test_cef_by_default(self):
        self.assertEqual(spz.config.csa.output_format.default, "CEF")

    def test_cef_when_asked(self):
        self.assertEqual(delivery_format(SimpleNamespace(is_istp=True), "CEF"), "CEF")

    def test_cdf_istp_when_asked_and_csa_has_it(self):
        self.assertEqual(delivery_format(SimpleNamespace(is_istp=True), "CDF_ISTP"), "CDF_ISTP")

    def test_case_does_not_matter(self):
        self.assertEqual(delivery_format(SimpleNamespace(is_istp=True), "cdf_istp"), "CDF_ISTP")

    def test_cef_when_csa_only_has_cef(self):
        self.assertEqual(delivery_format(SimpleNamespace(is_istp=False), "CDF_ISTP"), "CEF")

    def test_cdf_istp_for_inventories_older_than_the_flag(self):
        self.assertEqual(delivery_format(SimpleNamespace(), "CDF_ISTP"), "CDF_ISTP")

    def test_unknown_format_says_which_ones_exist(self):
        dataset = SimpleNamespace(is_istp=True)
        with self.assertRaisesRegex(ValueError, "CEF.*CDF_ISTP"):
            delivery_format(dataset, "NETCDF")


class CSAEachFormatHasItsOwnCacheAndProxyRequest(unittest.TestCase):
    def test_cdf_istp_keeps_the_cache_entries_written_before_cef_support(self):
        self.assertEqual(cache_entry_name("csa", "DS/VAR", "2005", output_format="CDF_ISTP"), "csa/DS/VAR/2005")

    def test_cef_has_its_own_cache_entries(self):
        self.assertEqual(cache_entry_name("csa", "DS/VAR", "2005", output_format="CEF"), "csa/DS/VAR-cef/2005")

    def test_the_data_index_stores_the_format_asked(self):
        from speasy.data_providers.csa import CsaWebservice
        self.assertEqual(CsaWebservice.request_options(output_format="cef"), {"output_format": "CEF"})
        self.assertEqual(CsaWebservice.request_options(), {})

    def test_the_proxy_is_asked_for_the_same_format(self):
        args = get_parameter_args(datetime(2005, 1, 1), datetime(2005, 1, 2), "DS/VAR", output_format="CEF")
        self.assertEqual(args["output_format"], "CEF")


def _csa_like_archive(content: bytes) -> io.BytesIO:
    """CSA answers with a gzipped tar: a download folder, then the file."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        folder = tarfile.TarInfo("CSA_Download/C1_CP_TEST")
        folder.type = tarfile.DIRTYPE
        tar.addfile(folder)
        member = tarfile.TarInfo("CSA_Download/C1_CP_TEST/C1_CP_TEST__V01.cef")
        member.size = len(content)
        tar.addfile(member, io.BytesIO(content))
    buffer.seek(0)
    return buffer


class CSAArchive(unittest.TestCase):
    def test_reads_the_file_inside_the_archive(self):
        v = _load_variable(_csa_like_archive(SCALAR), "density", get_codec("cef"))
        self.assertEqual(len(v), 3)

    def test_empty_archive_gives_none(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz"):
            pass
        buffer.seek(0)
        self.assertIsNone(_load_variable(buffer, "density", get_codec("cef")))


class CSALiveCef(unittest.TestCase):
    """Builds the inventory without the proxy: a proxy older than the CEF codec doesn't list CEF-only datasets."""

    @classmethod
    def setUpClass(cls):
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        spz.csa.update_inventory()

    @classmethod
    def tearDownClass(cls):
        os.environ.pop(spz.config.proxy.enabled.env_var_name)

    def test_cef_only_product(self):
        v = spz.get_data("csa/C1_CP_AUX_LSTAR/Lstar_value__C1_CP_AUX_LSTAR", "2005-01-01T00:00:00",
                         "2005-01-01T02:00:00", disable_cache=True)
        self.assertEqual(len(v), 120)
        self.assertEqual(v.unit, "unitless")

    def test_cef_by_default_even_where_csa_has_cdf_istp(self):
        v = spz.get_data("csa/C1_CP_FGM_SPIN/B_vec_xyz_gse__C1_CP_FGM_SPIN", "2005-01-01T00:00:00",
                         "2005-01-01T02:00:00", disable_cache=True)
        self.assertEqual(v.values.shape, (1737, 3))
        self.assertListEqual(v.columns, ["Bx", "By", "Bz"])
        self.assertIn("PARAMETER_TYPE", v.meta)  # a CEF attribute

    def test_cdf_istp_on_request(self):
        v = spz.get_data("csa/C1_CP_FGM_SPIN/B_vec_xyz_gse__C1_CP_FGM_SPIN", "2005-01-01T00:00:00",
                         "2005-01-01T02:00:00", disable_cache=True, output_format="CDF_ISTP")
        self.assertEqual(v.values.shape, (1737, 3))
        self.assertNotIn("PARAMETER_TYPE", v.meta)

    def test_cdf_istp_from_the_config(self):
        os.environ[spz.config.csa.output_format.env_var_name] = "CDF_ISTP"
        try:
            v = spz.get_data("csa/C1_CP_FGM_SPIN/B_vec_xyz_gse__C1_CP_FGM_SPIN", "2005-01-01T00:00:00",
                             "2005-01-01T02:00:00", disable_cache=True)
        finally:
            os.environ.pop(spz.config.csa.output_format.env_var_name)
        self.assertNotIn("PARAMETER_TYPE", v.meta)

    def test_cef_only_product_with_cdf_istp_asked(self):
        v = spz.get_data("csa/C1_CP_AUX_LSTAR/Lstar_value__C1_CP_AUX_LSTAR", "2005-01-01T00:00:00",
                         "2005-01-01T02:00:00", disable_cache=True, output_format="CDF_ISTP")
        self.assertEqual(len(v), 120)

    def test_cef_and_cdf_istp_give_the_same_variable(self):
        args = ("https://csa.esac.esa.int/csa-sl-tap/data", "C1_CP_FGM_SPIN", "B_vec_xyz_gse__C1_CP_FGM_SPIN",
                spz.core.make_utc_datetime("2005-01-01T00:00:00"), spz.core.make_utc_datetime("2005-01-01T02:00:00"))
        cef, cdf = _download_variable(*args, delivery_format="CEF"), _download_variable(*args, delivery_format="CDF_ISTP")
        np.testing.assert_array_equal(cef.time, cdf.time)
        np.testing.assert_array_equal(cef.values, cdf.values)
        self.assertListEqual(cef.columns, cdf.columns)
        self.assertEqual(cef.unit, cdf.unit)


if __name__ == '__main__':
    unittest.main()
