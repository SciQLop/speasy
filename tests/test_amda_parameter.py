#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package parameter getting functions."""

import unittest
import os
from datetime import datetime, timezone
from speasy.amda import AMDA, load_csv
from speasy.common.variable import SpeasyVariable
from ddt import ddt, data
import numpy as np

from speasy.amda.dataset import Dataset
from speasy.amda.parameter import Parameter

@ddt
class SimpleRequest(unittest.TestCase):
    def setUp(self):
        self.ws = AMDA()
        self.start=datetime(2000,1,1,1,1)
        self.stop=datetime(2000,1,1,1,2)
        self.data = self.ws.get_parameter("imf", self.start, self.stop)
        self.dataset = self.ws.get_dataset("ace-imf-all", self.start, self.stop)


    def tearDown(self):
        pass
    # check that the data is not None
    def test_data_not_none(self):
        self.assertIsNotNone(self.data)
    # check that values are not empty
    def test_data_not_empty(self):
        self.assertTrue(len(self.data.values.shape)>0)
    # check that time is not empty
    def test_time_not_empty(self):
        self.assertTrue(len(self.data.time.shape)>0)
    # check that time and data have compatible shapes
    def test_data_time_compatibility(self):
        self.assertTrue( self.data.values.shape[0]==self.data.time.shape[0])
    # check that time is of type float
    def test_time_datatype(self):
        self.assertTrue( self.data.time.dtype == float )
    # check that start and stop times are correct
    # NOTE : in AMDA when requesting data between t1 and t2 the resulting array represents the
    #        time period [t1,t2] (note the inclusion of t2).
    def test_time_range(self):
        self.assertTrue( datetime.utcfromtimestamp(self.data.time[0])==self.start )
        self.assertTrue( datetime.utcfromtimestamp(self.data.time[-1])==self.stop )


    ## Dataset tests
    # check that the dataset is not none
    def test_dataset_not_none(self):
        self.assertIsNotNone(self.dataset)
    # check that the dataset object is a list
    def test_dataset_type(self):
        self.assertTrue(isinstance(self.dataset, Dataset))
    # check that dataset is not empty
    def test_dataset_not_empty(self):
        self.assertTrue(len(self.dataset)>0)
    # check that every item of the dataset is a SpeasyVariable object
    def test_dataset_items_datatype(self):
        for item in self.dataset.parameters:
            self.assertTrue(isinstance(self.dataset.parameters[item], SpeasyVariable))
    # check that all items in the dataset have the same time dimensions
    ##def test_dataset_items_dimensions(self):
    ##    c=None
    ##    for item in self.dataset:
    ##        if len(item.time.shape)==0:
    ##            # empty variable
    ##            c=None
    ##            break
    ##        else:
    ##            if c is None:
    ##                c=item.time.shape
    ##            else:
    ##                if any(item.time.shape!=c):
    ##                    c=None
    ##                    break
    ##    self.assertIsNotNone(c)
                


if __name__ == '__main__':
    unittest.main()
