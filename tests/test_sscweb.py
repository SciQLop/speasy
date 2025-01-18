#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import os
import unittest
from datetime import datetime, timezone
import numpy as np
from ddt import data, ddt

from speasy.data_providers import ssc
from speasy.products import SpeasyVariable

_HERE_ = os.path.dirname(os.path.abspath(__file__))


@ddt
class SscWeb(unittest.TestCase):
    def setUp(self):
        self.ssc = ssc.SSC_Webservice()

    def tearDown(self):
        pass

    def test_parses_xml_inventory(self):
        with open(os.path.join(_HERE_, 'resources', 'sscweb_observatories.xml')) as f:
            inventory = ssc.parse_inventory(f.read())
            self.assertIsNotNone(inventory)
            self.assertGreater(len(inventory), 0)
            for item in inventory:
                self.assertIsInstance(item, dict)
                self.assertIn('Id', item)
                self.assertIsInstance(item['Id'], str)
                self.assertIn('Name', item)
                self.assertIsInstance(item['Name'], str)
                self.assertIn('StartTime', item)
                self.assertIsInstance(item['StartTime'], str)
                self.assertIn('EndTime', item)
                self.assertIsInstance(item['EndTime'], str)
                self.assertIn('Resolution', item)
                self.assertIsInstance(item['Resolution'], str)

    def test_parses_xml_trajectory(self):
        with open(os.path.join(_HERE_, 'resources', 'sscweb_trajectory.xml')) as f:
            trajectory = ssc.parse_trajectory(f.read())
            self.assertIsNotNone(trajectory)
            self.assertGreater(len(trajectory), 0)
            self.assertIsInstance(trajectory, SpeasyVariable)
            self.assertIn('X', trajectory.columns)
            self.assertIn('Y', trajectory.columns)
            self.assertIn('Z', trajectory.columns)
            self.assertIn('CoordinateSystem', trajectory.meta)
            self.assertEqual(trajectory.meta['CoordinateSystem'], 'GSE')
            self.assertEqual(trajectory.meta['UNITS'], 'km')
            self.assertEqual(trajectory.time[0], np.datetime64('2006-01-08T01:00:00.000000000', 'ns'))
            self.assertIsInstance(trajectory.values[0][0], np.float64)

    @data(
        {
            "product": "moon",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "bepicolombo",
            "start_time": datetime(2019, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2019, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc),
            "coordinate_system": "GSE"
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc),
            "coordinate_system": "gse"
        }
    )
    def test_get_orbit(self, kw):
        result = self.ssc.get_data(**kw,
                                   debug=True,
                                   disable_cache=True,
                                   disable_proxy=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        self.assertGreater(np.timedelta64(60, 's'), np.datetime64(kw["start_time"], 'ns') - result.time[0])
        self.assertGreater(np.timedelta64(60, 's'), np.datetime64(kw["stop_time"], 'ns') - result.time[-1])

    def test_returns_none_for_a_request_outside_of_range(self):
        with self.assertLogs('speasy.core.dataprovider', level='WARNING') as cm:
            result = self.ssc.get_data('solarorbiter', datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
                                       datetime(2006, 1, 8, 2, 0, 0, tzinfo=timezone.utc))
            self.assertIsNone(result)
            self.assertTrue(
                any(["outside of its definition range" in line for line in cm.output]))

    def test_get_observatories(self):
        obs_list = self.ssc.get_observatories(force_refresh=True)
        self.assertIsNotNone(obs_list)
        self.assertGreater(len(obs_list), 10)  # it has to return few elements
        for item in obs_list:
            self.assertIsInstance(item, dict)
            self.assertIn('Id', item)
            self.assertIsInstance(item['Id'], str)
            self.assertIn('Name', item)
            self.assertIsInstance(item['Name'], str)
            self.assertIn('StartTime', item)
            self.assertIsInstance(item['StartTime'], str)
            self.assertIn('EndTime', item)
            self.assertIsInstance(item['EndTime'], str)
            self.assertIn('Resolution', item)
            self.assertIsInstance(item['Resolution'], str)

    @data({'sampling': '1'},
          {'unknown_arg': 10})
    def test_raises_if_user_passes_unexpected_kwargs_to_get_orbit(self, kwargs):
        with self.assertRaises(TypeError):
            self.ssc.get_data('moon', "2018-01-01", "2018-01-02", **kwargs)


class SscWebTrajectoriesPlots(unittest.TestCase):
    def setUp(self):
        import speasy as spz
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            self.skipTest("Can't import matplotlib")
        self.traj: spz.SpeasyVariable = spz.get_data(spz.inventories.data_tree.ssc.Trajectories.ace, "2018-01-01",
                                                     "2018-01-02")

    def tearDown(self):
        pass

    def test_should_be_able_to_plot_a_trajectory(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ax = self.traj.plot()
        self.assertIsNotNone(ax)

    def test_units_must_be_in_axis_label(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ax = self.traj.plot()
        self.assertIsNotNone(ax)
        self.assertIn("km", ax.get_ylabel())

    def test_legend_is_set_with_variable_columns_names(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ax = self.traj.plot()
        self.assertIsNotNone(ax)
        self.assertIn(self.traj.columns[0], ax.get_legend().texts[0].get_text())
        self.assertIn(self.traj.columns[1], ax.get_legend().texts[1].get_text())
        self.assertIn(self.traj.columns[2], ax.get_legend().texts[2].get_text())


if __name__ == '__main__':
    unittest.main()
