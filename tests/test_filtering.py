#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `signal.filtering` package."""

import unittest

from datetime import datetime

import numpy as np

from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer
from speasy.signal.filtering import sosfiltfilt
from speasy.signal.resampling import generate_time_vector
from scipy.signal import iirfilter


class TestSimpleLowPassFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = datetime(2000, 1, 1, 1, 1)
        cls.stop = datetime(2000, 1, 1, 1, 2)
        time_vec = generate_time_vector(cls.start, cls.stop, np.timedelta64(1, 'ms'))
        x = (np.arange(len(time_vec)) / len(time_vec)) * np.pi * 2
        cls.data = SpeasyVariable(
            axes=[VariableTimeAxis(values=time_vec)],
            values=DataContainer(
                np.sin(x) + np.sin(10000 * x)
            )
        )
        cls.sos = iirfilter(6, 0.1, btype='low', rs=80, ftype='cheby2', output='sos')
        cls.filtered = sosfiltfilt(cls.sos, cls.data)
        cls.ideal = np.sin(x)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_filtering_does_not_change_length(self):
        self.assertEqual(len(self.filtered.time), len(self.data))

    def test_filtered_values(self):
        self.assertTrue(np.allclose(self.filtered[1000:-1000], self.ideal[1000:-1000].reshape((-1, 1)), rtol=1e-10))
