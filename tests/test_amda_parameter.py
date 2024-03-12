#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package parameter getting functions."""

import unittest
from ddt import data, ddt
from datetime import datetime, timedelta

import numpy as np

import speasy as spz
from speasy.core import make_utc_datetime


class ParameterRequests(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.start = datetime(2000, 1, 1, 1, 1)
        self.stop = datetime(2000, 1, 1, 1, 2)
        self.data = spz.amda.get_parameter(
            "imf", self.start, self.stop, disable_proxy=True, disable_cache=True)
        self.dataset = spz.amda.get_dataset(
            "ace-imf-all", self.start, self.stop, disable_proxy=True, disable_cache=True)

    @classmethod
    def tearDownClass(self):
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
        self.assertTrue(isinstance(self.dataset, spz.Dataset))

    def test_dataset_not_empty(self):
        self.assertTrue(len(self.dataset) > 0)

    def test_dataset_items_datatype(self):
        for item in self.dataset:
            self.assertTrue(isinstance(self.dataset[item], spz.SpeasyVariable))

    def test_restricted_time_range(self):
        from speasy.webservices.amda._impl import credential_are_valid
        if credential_are_valid():
            self.skipTest("Should only run when credentials are not valid")
        dataset = None
        for dataset in spz.inventories.flat_inventories.amda.datasets.values():
            if hasattr(dataset, 'timeRestriction'):
                break
        if dataset is not None:
            from speasy.webservices.amda.exceptions import MissingCredentials
            from speasy.core import make_utc_datetime
            with self.assertRaises(MissingCredentials):
                spz.amda.get_dataset(dataset, make_utc_datetime(dataset.timeRestriction),
                                     make_utc_datetime(dataset.timeRestriction) + timedelta(minutes=1))

    def test_restricted_time_range_after_stop_date(self):
        dataset = None
        for dataset in spz.inventories.flat_inventories.amda.datasets.values():
            if hasattr(dataset, 'timeRestriction'):
                if make_utc_datetime(dataset.timeRestriction) > make_utc_datetime(dataset.stop_date):
                    break
        if dataset is not None:
            spz.amda.get_dataset(dataset, make_utc_datetime(dataset.timeRestriction) - timedelta(days=10),
                                 make_utc_datetime(dataset.timeRestriction) - timedelta(days=10) + timedelta(minutes=1), disable_proxy=True, disable_cache=True)


@ddt
class AMDAParametersPlots(unittest.TestCase):
    def setUp(self):
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            self.skipTest("Can't import matplotlib")

    @data(
        spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_mag,
        spz.inventories.tree.amda.Parameters.MMS.MMS3.FPI.fast_mode.mms3_fpi_desmoms.mms3_des_tpara,
        spz.inventories.tree.amda.Parameters.THEMIS.THEMIS_A.ESA.tha_peim_all.tha_n_peim
    )
    def test_parameter_line_plot(self, parameter):
        values: spz.SpeasyVariable = spz.get_data(parameter, "2018-01-01", "2018-01-01T01")
        import matplotlib.pyplot as plt
        plt.close('all')
        ax = values.plot()
        self.assertIsNotNone(ax)
        self.assertEqual(len(ax.lines), values.values.shape[1],
                         "Number of lines in the plot should be equal to the number of columns in the data")
        self.assertIn(values.unit, ax.get_ylabel(), "Units should be in the Y axis label")
        for i, name in enumerate(values.columns):
            self.assertIn(name, ax.get_legend().texts[i].get_text(), "Legend should contain the column names")

    @data(
        spz.inventories.tree.amda.Parameters.MMS.MMS1.FPI.fast_mode.mms1_fpi_desmoms.mms1_des_omni,
        spz.inventories.tree.amda.Parameters.MAVEN.STATIC.mavpds_sta_c6.mav_sta_c6_energy
    )
    def test_parameter_colormap_lot(self, parameter):
        values: spz.SpeasyVariable = spz.get_data(parameter, "2018-01-01", "2018-01-01T01")
        import matplotlib.pyplot as plt
        plt.close('all')
        ax = values.plot()
        self.assertIsNotNone(ax)
        self.assertIn(values.axes[1].unit, ax.get_ylabel(), "Units should be in the Y axis label")


if __name__ == '__main__':
    unittest.main()
