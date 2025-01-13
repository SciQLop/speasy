#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.common` package."""
import unittest
import numpy as np

from ddt import ddt, data, unpack

import speasy as spz
from speasy.core.cache import entries


@ddt
class Listify(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        ("some text", ["some text"]),
        ([1], [1]),
        ((1, 2), [1, 2])
    )
    @unpack
    def test_listify(self, input, expected):
        self.assertEqual(spz.core.listify(input), expected)


class Indexes(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_parameter_index_contains_component(self):
        self.assertIn(spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm.imf_gsm0,
                      spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm)

        self.assertNotIn(spz.inventories.tree.amda.Parameters.ACE.MFI.ace_mag_real.imf_real_gse.imf_real_gse1,
                         spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm)

        self.assertNotIn("random name that is not a component",
                         spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm)

    def test_dataset_index_contains_parameter(self):
        self.assertIn(spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm,
                      spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all)

        self.assertNotIn(spz.inventories.tree.amda.Parameters.ACE.MFI.ace_mag_real.imf_real_gse,
                         spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all)

        self.assertNotIn("random name that is not a parameter",
                         spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all)


@ddt
class TestTimeConversions(unittest.TestCase):

    @data(
        (np.array(['1970-01-01T00:00:00.000000000', '1970-01-01T00:00:01.000000000'], dtype='datetime64[ns]'),
         np.array([0., 1.])),
        (np.array(['1970-01-01T00:00:00.000000000', '1970-01-01T00:00:01.000000001'], dtype='datetime64[ns]'),
         np.array([0., 1.000000001])),
        (np.array(['2040-01-01T00:00:00.000000000', '2040-01-01T00:00:01.000000001'], dtype='datetime64[ns]'),
         np.array([2208985200.0, 2208985201.000000001])),
    )
    @unpack
    def test_dt64_to_epoch(self, input, expected):
        self.assertTrue(np.allclose(spz.core.datetime64_to_epoch(input), expected, atol=1e-10))

    @data(
        (np.array([0., 1.]),
         np.array(['1970-01-01T00:00:00.000000000', '1970-01-01T00:00:01.000000000'], dtype='datetime64[ns]')),
        (np.array([0., 1.000000001]),
         np.array(['1970-01-01T00:00:00.000000000', '1970-01-01T00:00:01.000000001'], dtype='datetime64[ns]')),
        (np.array([2208985200.0, 2208985201.000000001]),
         np.array(['2040-01-01T00:00:00.000000000', '2040-01-01T00:00:01.000000001'], dtype='datetime64[ns]')),
    )
    @unpack
    def test_epoch_to_dt64(self, input, expected):
        self.assertTrue(
            np.allclose(spz.core.epoch_to_datetime64(input).astype('int64'), expected.astype('int64'), atol=1e-10))


class TestDroppingKeysFromCache(unittest.TestCase):

    def test_dropping_specific_key(self):
        spz.core.cache.add_item("key1", "value1")
        spz.core.cache.add_item("key2", "value2")
        spz.core.cache.add_item("key3", "value3")

        spz.core.cache.drop_item("key2")

        self.assertEqual(spz.core.cache.get_item("key1"), "value1")
        self.assertIsNone(spz.core.cache.get_item("key2"))
        self.assertEqual(spz.core.cache.get_item("key3"), "value3")
        spz.core.cache.drop_matching_entries("key\\d")

    def test_dropping_matching_keys(self):
        spz.core.cache.add_item("key1", "value1")
        spz.core.cache.add_item("key2", "value2")
        spz.core.cache.drop_matching_entries("key\\d")
        self.assertIsNone(spz.core.cache.get_item("key1"))
        self.assertIsNone(spz.core.cache.get_item("key2"))

    def test_dropping_speasy_variables(self):
        spz.get_data(spz.inventories.tree.ssc.Trajectories.ace, "2008-01-01", "2008-01-02")
        self.assertGreater(len(list(filter(lambda e: e.startswith("ssc_orbits/ace/gse"), spz.core.cache.entries()))), 0)
        spz.core.cache.drop_matching_entries("^ssc_orbits/ace/gse")
        self.assertEqual(len(list(filter(lambda e: e.startswith("ssc_orbits/ace/gse"), spz.core.cache.entries()))), 0)


if __name__ == '__main__':
    unittest.main()
