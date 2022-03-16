#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package timetable implementation."""

import unittest
import speasy as spz
from speasy.core.datetime_range import DateTimeRange


class CatalogRequests(unittest.TestCase):
    def setUp(self):
        self.cat = spz.amda.get_catalog("sharedcatalog_33")

    def tearDown(self):
        pass

    def test_catalog_shape(self):
        self.assertTrue(len(self.cat) > 0)

    def test_catalog_has_a_name(self):
        self.assertIsNot(self.cat.name, "listOfICMEs_Nguyen")

    def test_is_convertible_to_dataframe(self):
        df = self.cat.to_dataframe()
        self.assertTrue(len(df) > 0)
        self.assertListEqual(list(df.columns), ['start_time', 'stop_time', 'col3'])


if __name__ == '__main__':
    unittest.main()
