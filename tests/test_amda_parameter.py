#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package parameter getting functions."""

import unittest
from datetime import datetime, timedelta
import speasy as spz
from speasy.common.variable import SpeasyVariable

from speasy.amda.dataset import Dataset


class ParameterRequests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2000, 1, 1, 1, 1)
        self.stop = datetime(2000, 1, 1, 1, 2)
        self.data = spz.amda.get_parameter("imf", self.start, self.stop)
        self.dataset = spz.amda.get_dataset("ace-imf-all", self.start, self.stop)

    def tearDown(self):
        pass

    def test_data_not_none(self):
        self.assertIsNotNone(self.data)

    def test_data_not_empty(self):
        self.assertTrue(len(self.data.values.shape) > 0)

    def test_time_not_empty(self):
        self.assertTrue(len(self.data.time.shape) > 0)

    def test_data_time_compatibility(self):
        self.assertTrue(self.data.values.shape[0] == self.data.time.shape[0])

    def test_time_datatype(self):
        self.assertTrue(self.data.time.dtype == float)

    def test_time_range(self):
        min_dt = min(self.data.time[1:] - self.data.time[:-1])
        self.assertTrue(
            self.start <= datetime.utcfromtimestamp(self.data.time[0]) < self.start + timedelta(seconds=min_dt))
        self.assertTrue(
            self.stop > datetime.utcfromtimestamp(self.data.time[-1]) >= self.stop - timedelta(seconds=min_dt))

    def test_dataset_not_none(self):
        self.assertIsNotNone(self.dataset)

    def test_dataset_type(self):
        self.assertTrue(isinstance(self.dataset, Dataset))

    def test_dataset_not_empty(self):
        self.assertTrue(len(self.dataset) > 0)

    def test_dataset_items_datatype(self):
        for item in self.dataset.parameters:
            self.assertTrue(isinstance(self.dataset.parameters[item], SpeasyVariable))


if __name__ == '__main__':
    unittest.main()
