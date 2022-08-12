#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package parameter getting functions."""

import unittest
from datetime import datetime

import numpy as np

import speasy as spz
from speasy.products.variable import SpeasyVariable

from speasy.products.dataset import Dataset


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
        self.assertTrue(self.data.time.dtype == np.dtype('datetime64[ns]'))

    def test_time_range(self):
        min_dt = min(self.data.time[1:] - self.data.time[:-1])
        start = np.datetime64(self.start, 'ns')
        stop = np.datetime64(self.stop, 'ns')
        self.assertTrue(
            start <= self.data.time[0] < (start + min_dt))
        self.assertTrue(
            stop > self.data.time[-1] >= (stop - min_dt))

    def test_dataset_not_none(self):
        self.assertIsNotNone(self.dataset)

    def test_dataset_type(self):
        self.assertTrue(isinstance(self.dataset, Dataset))

    def test_dataset_not_empty(self):
        self.assertTrue(len(self.dataset) > 0)

    def test_dataset_items_datatype(self):
        for item in self.dataset:
            self.assertTrue(isinstance(self.dataset[item], SpeasyVariable))


if __name__ == '__main__':
    unittest.main()
