#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""
import logging
import unittest
from ddt import ddt, data, unpack
import os
from datetime import datetime, timezone
import speasy as spz
from speasy.webservices.amda.utils import load_csv
from speasy.webservices.amda import ProductType
from speasy.webservices.amda.inventory import AmdaXMLParser, to_xmlid
from speasy.webservices.amda.exceptions import MissingCredentials
from speasy.inventories import flat_inventories


def has_amda_creds() -> bool:
    return spz.config.amda.username() != "" and spz.config.amda.password() != ""


class UserProductsRequestsWithoutCreds(unittest.TestCase):
    def setUp(self):
        os.environ[spz.config.amda.username.env_var_name] = ""
        os.environ[spz.config.amda.password.env_var_name] = ""

    def tearDown(self):
        os.environ.pop(spz.config.amda.username.env_var_name)
        os.environ.pop(spz.config.amda.password.env_var_name)

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
        with self.assertLogs('speasy.webservices.amda.rest_client', level='WARNING') as cm:
            start_date = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            stop_date = datetime(2021, 1, 30, 0, 0, 0, tzinfo=timezone.utc)
            parameter_id = "mms1_b_gse"
            result = spz.amda.get_parameter(parameter_id, start_date, stop_date, disable_proxy=True, disable_cache=True)
            self.assertIsNotNone(result)
            self.assertTrue(
                any(["This request duration is too long, consider reducing time range" in line for line in cm.output]))

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
        r = spz.amda.get_data("psp_spe_EvsEvspa", "2021-07-30T00:00:00", "2021-07-30T00:05:00")
        self.assertIsNotNone(r)
        self.assertIsNotNone(r.data)


class PrivateProductsRequests(unittest.TestCase):
    def setUp(self):
        if not has_amda_creds():
            self.skipTest("Missing AMDA_Webservice credentials")

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
        result = spz.amda.get_user_parameter(spz.amda.list_user_parameters()[0], start_time="2016-06-01",
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

    def test_loads_csv(self):
        var = load_csv(f'{os.path.dirname(os.path.abspath(__file__))}/resources/amda_sample_spectro.txt')
        self.assertEqual(var.values.shape[0], len(var.time))
        self.assertEqual(var.values.shape[1], len(var.columns))
        self.assertGreater(len(var.time), 0)
        self.assertTrue('MISSION_ID' in var.meta)

    def test_load_obs_datatree(self):
        with open(f'{os.path.dirname(os.path.abspath(__file__))}/resources/obsdatatree.xml') as obs_xml:
            flat_inventories.amda.parameters.clear()
            flat_inventories.amda.datasets.clear()
            root = AmdaXMLParser.parse(obs_xml.read(), is_public=True)
            # grep -o -i '<parameter ' obsdatatree.xml | wc -l
            self.assertEqual(len(spz.amda.list_parameters()), 4696)
            # grep -o -i '<dataset ' obsdatatree.xml | wc -l
            self.assertEqual(len(spz.amda.list_datasets()), 935)

    @data(
        (spz.amda.list_catalogs()[-1], ProductType.CATALOG),
        (to_xmlid(spz.amda.list_catalogs()[-1]), ProductType.CATALOG),
        (spz.amda.list_timetables()[-1], ProductType.TIMETABLE),
        (to_xmlid(spz.amda.list_timetables()[-1]), ProductType.TIMETABLE),
        (spz.amda.list_datasets()[-1], ProductType.DATASET),
        (to_xmlid(spz.amda.list_datasets()[-1]), ProductType.DATASET),
        (spz.inventories.data_tree.amda.Parameters.ACE.Ephemeris.ace_orb_all.ace_xyz_gse.ace_xyz_gse0,
         ProductType.COMPONENT),
        (to_xmlid(spz.inventories.data_tree.amda.Parameters.ACE.Ephemeris.ace_orb_all.ace_xyz_gse.ace_xyz_gse0),
         ProductType.COMPONENT),
        ('this xml id is unlikely to exist', ProductType.UNKNOWN),
        (spz.inventories.data_tree.amda.Parameters.ACE, ProductType.UNKNOWN)
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


if __name__ == '__main__':
    unittest.main()
