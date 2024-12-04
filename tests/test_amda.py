#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""
import os
import unittest
from datetime import datetime, timezone

import numpy as np
import speasy as spz
from ddt import data, ddt, unpack
from speasy.config import amda as amda_cfg
from speasy.inventories import flat_inventories
from speasy.products import SpeasyVariable
from speasy.core.impex import ImpexProductType
from speasy.core.impex.exceptions import MissingCredentials
from speasy.core.impex.parser import ImpexXMLParser, to_xmlid

_HERE_ = os.path.dirname(os.path.abspath(__file__))


def has_amda_creds() -> bool:
    return spz.config.amda.username() != "" and spz.config.amda.password() != ""


class UserProductsRequestsWithoutCreds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if has_amda_creds():
            spz.amda.reset_credentials()

    @classmethod
    def tearDownClass(cls):
        if has_amda_creds():
            spz.amda.reset_credentials(spz.config.amda.username(), spz.config.amda.password())

    def test_get_user_timetables(self):
        with self.assertRaises(MissingCredentials):
            spz.amda.get_user_timetable("Id doesn't matter")

    def test_get_user_parameters(self):
        with self.assertRaises(MissingCredentials):
            spz.amda.get_user_parameter("Id doesn't matter", start_time="2016-06-01", stop_time="2016-06-01T12:00:00")

    def test_get_user_catalogs(self):
        with self.assertRaises(MissingCredentials):
            spz.amda.get_user_catalog("Id doesn't matter")


class PublicProductsRequests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_variable(self):
        start_date = datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 8, 1, 0, 10, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = spz.amda.get_parameter(parameter_id, start_date, stop_date, disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)
        start_date = datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2016, 1, 8, 1, 0, 10, tzinfo=timezone.utc)
        parameter_id = "c1_hia_prest"
        result = spz.amda.get_parameter(parameter_id, start_date, stop_date, disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)

    def test_get_variable_over_midnight(self):
        start_date = datetime(2006, 1, 8, 23, 30, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 9, 0, 30, 0, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = spz.amda.get_parameter(parameter_id, start_date, stop_date, disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)

    def test_get_variable_long_request(self):
        if "SPEASY_LONG_TESTS" not in os.environ:
            self.skipTest("Long tests disabled")
        else:
            self.skipTest("Long tests not implemented")

    def test_returns_none_for_a_request_outside_of_range(self):
        with self.assertLogs('speasy.core.dataprovider', level='WARNING') as cm:
            start_date = datetime(1999, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            stop_date = datetime(1999, 1, 30, 0, 0, 0, tzinfo=timezone.utc)
            parameter_id = "mms1_b_gse"
            result = spz.amda.get_parameter(parameter_id, start_date, stop_date, disable_proxy=True, disable_cache=True)
            self.assertIsNone(result)
            self.assertTrue(
                any(["outside of its definition range" in line for line in cm.output]))

    def test_get_product_range(self):
        param_range = spz.amda.parameter_range(spz.amda.list_parameters()[0])
        self.assertIsNotNone(param_range)
        dataset_range = spz.amda.dataset_range(spz.amda.list_datasets()[0])
        self.assertIsNotNone(dataset_range)

    def test_list_parameters(self):
        result = spz.amda.list_parameters()
        self.assertTrue(len(result) != 0)

    def test_get_parameter(self):
        start, stop = datetime(2000, 1, 1), datetime(2000, 1, 2)
        r = spz.amda.get_parameter("imf", start, stop, disable_cache=True)
        self.assertIsNotNone(r)

    def test_get_parameter_as_cdf(self):
        start, stop = datetime(2000, 1, 1), datetime(2000, 1, 2)
        r: SpeasyVariable = spz.amda.get_parameter("imf", start, stop, disable_cache=True, disable_proxy=True,
                                                   output_format="CDF_ISTP")
        self.assertEqual(r.name, "imf")
        self.assertEqual(r.columns, ['bx', 'by', 'bz'])
        self.assertEqual(r.unit, "nT")
        self.assertIsNotNone(r)

    def test_list_datasets(self):
        result = spz.amda.list_datasets()
        self.assertTrue(len(result) != 0)

    def test_get_dataset(self):
        start, stop = datetime(2012, 1, 1), datetime(2012, 1, 1, 1)
        r = spz.amda.get_dataset("tao-ura-sw", start, stop, disable_cache=True)
        self.assertTrue(len(r) != 0)

    def test_list_timetables(self):
        result = spz.amda.list_timetables()
        self.assertTrue(len(result) != 0)

    def test_get_sharedtimeTable_0(self):
        r = spz.amda.get_timetable("sharedtimeTable_0")
        self.assertIsNotNone(r)

    def test_get_timetable_from_Index(self):
        r = spz.amda.get_timetable(spz.amda.list_timetables()[-1])
        self.assertIsNotNone(r)

    def test_get_catalog_from_Index(self):
        r = spz.amda.get_catalog(spz.amda.list_catalogs()[-1])
        self.assertIsNotNone(r)

    def test_get_multidimensional_data(self):
        for f in ("CDF_ISTP",):
            r = spz.amda.get_data("psp_spe_EvsE", "2021-07-30T00:00:00", "2021-07-30T00:05:00", output_format=f)
            self.assertIsNotNone(r)
            self.assertIsNotNone(r.values)


class PrivateProductsRequests(unittest.TestCase):
    def setUp(self):
        if not has_amda_creds():
            self.skipTest("Missing AMDA_Webservice credentials")
        spz.amda.reset_credentials(spz.config.amda.username(), spz.config.amda.password())

    def tearDown(self):
        pass

    def test_list_user_timetables(self):
        result = spz.amda.list_user_timetables()
        self.assertTrue(len(result) != 0)

    def test_list_user_parameters(self):
        result = spz.amda.list_user_parameters()
        self.assertTrue(len(result) != 0)

    def test_list_user_catalogs(self):
        result = spz.amda.list_user_catalogs()
        self.assertTrue(len(result) != 0)

    def test_get_user_timetables(self):
        result = spz.amda.get_user_timetable(spz.amda.list_user_timetables()[0])
        self.assertIsNotNone(result)
        self.assertTrue(len(result) != 0)

    def test_get_user_parameters(self):
        for method in (spz.amda.get_user_parameter, spz.amda.get_data):
            result = method(spz.amda.list_user_parameters()[0], start_time="2016-06-01",
                            stop_time="2016-06-01T12:00:00")
            self.assertIsNotNone(result)
            self.assertTrue(len(result) != 0)

    def test_get_user_catalogs(self):
        result = spz.amda.get_user_catalog(spz.amda.list_user_catalogs()[0])
        self.assertIsNotNone(result)
        self.assertTrue(len(result) != 0)


@ddt
class AMDAModule(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_load_obs_datatree(self):
        with open(os.path.normpath(f'{_HERE_}/resources/obsdatatree.xml')) as obs_xml:
            flat_inventories.amda.parameters.clear()
            flat_inventories.amda.datasets.clear()
            root = ImpexXMLParser.parse(obs_xml.read(), is_public=True, provider_name='amda')
            flat_inventories.amda.update(root)
            self.assertIsNotNone(root)
            # grep -o -i '<parameter ' obsdatatree.xml | wc -l
            self.assertEqual(len(spz.amda.list_parameters()), 4696)
            # grep -o -i '<dataset ' obsdatatree.xml | wc -l
            self.assertEqual(len(spz.amda.list_datasets()), 935)
        spz.update_inventories()

    @data(
        (spz.amda.list_catalogs()[-1], ImpexProductType.CATALOG),
        (to_xmlid(spz.amda.list_catalogs()[-1]), ImpexProductType.CATALOG),
        (spz.amda.list_timetables()[-1], ImpexProductType.TIMETABLE),
        (to_xmlid(spz.amda.list_timetables()[-1]), ImpexProductType.TIMETABLE),
        (spz.amda.list_datasets()[-1], ImpexProductType.DATASET),
        (to_xmlid(spz.amda.list_datasets()[-1]), ImpexProductType.DATASET),
        (spz.inventories.data_tree.amda.Parameters.ACE.Ephemeris.ace_orb_all.ace_xyz_gse.ace_xyz_gse0,
         ImpexProductType.COMPONENT),
        (to_xmlid(spz.inventories.data_tree.amda.Parameters.ACE.Ephemeris.ace_orb_all.ace_xyz_gse.ace_xyz_gse0),
         ImpexProductType.COMPONENT),
        ('this xml id is unlikely to exist', ImpexProductType.UNKNOWN),
        (spz.inventories.data_tree.amda.Parameters.ACE, ImpexProductType.UNKNOWN)
    )
    @unpack
    def test_returns_product_type_from_either_id_or_index(self, index, expexted_type):
        result_type = spz.amda.product_type(index)
        self.assertEqual(result_type, expexted_type)

    @data({'sampling': '1'},
          {'unknown_arg': 10})
    def test_raises_if_user_passes_unexpected_kwargs_to_get_data(self, kwargs):
        with self.assertRaises(TypeError):
            spz.get_data('amda/c1_b_gsm', "2018-01-01", "2018-01-02", **kwargs)
        with self.assertRaises(TypeError):
            spz.amda.get_data('c1_b_gsm', "2018-01-01", "2018-01-02", **kwargs)

    def test_raises_if_user_passes_unknown_product_kwargs_to_get_data(self):
        with self.assertRaises(ValueError):
            spz.get_data('amda/This_product_does_not_exist')
        with self.assertRaises(ValueError):
            spz.get_data('amda/This_product_does_not_exist', "2018-01-01", "2018-01-02")

    def test_non_regression_CDF_ISTP_with_proxy_and_config(self):
        ref = spz.get_data(spz.inventories.tree.amda.Parameters.MMS.MMS1.FPI.fast_mode.mms1_fpi_dismoms.mms1_dis_omni,
                           "2021-06-01", "2021-06-08T02", output_format='CDF_ISTP')
        os.environ[amda_cfg.output_format.env_var_name] = 'CDF_ISTP'
        var = spz.get_data(spz.inventories.tree.amda.Parameters.MMS.MMS1.FPI.fast_mode.mms1_fpi_dismoms.mms1_dis_omni,
                           "2021-06-01", "2021-06-08T02")
        self.assertTrue(len(ref.axes), 2)
        self.assertTrue(len(var.axes), 2)
        self.assertTrue(np.all(var.axes[1].values == ref.axes[1].values))


if __name__ == '__main__':
    unittest.main()
