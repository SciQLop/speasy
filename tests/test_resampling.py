#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `signal.resampling` package."""

import unittest

from datetime import datetime

import numpy as np

from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer
from speasy.signal.resampling import resample, generate_time_vector, interpolate
from scipy.interpolate import InterpolatedUnivariateSpline


class TestGenerateTimeVector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dt = 500
        cls.start = datetime(2000, 1, 1, 1, 1)
        cls.stop = datetime(2000, 1, 1, 1, 2)
        cls.time_vector = generate_time_vector(cls.start, cls.stop, cls.dt / 1000)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_time_vector_length(self):
        self.assertEqual(len(self.time_vector), 120)

    def test_time_vector_datatype(self):
        self.assertEqual(self.time_vector.dtype, np.dtype('datetime64[ns]'))

    def test_time_vector_start(self):
        self.assertEqual(self.time_vector[0], np.datetime64(self.start, 'ns'))

    def test_time_vector_stop(self):
        self.assertEqual(self.time_vector[-1], np.datetime64(self.stop, 'ns') - np.timedelta64(int(self.dt), 'ms'))


class TestDownSampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = datetime(2000, 1, 1, 1, 1)
        cls.stop = datetime(2000, 1, 1, 1, 2)
        cls.data = SpeasyVariable(
            axes=[VariableTimeAxis(values=generate_time_vector(cls.start, cls.stop, 1))],
            values=DataContainer(np.arange(60.).reshape(-1, 1))
        )
        cls.resampled = resample(cls.data, 10)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_resampled_length(self):
        self.assertEqual(len(self.resampled.time), 6)

    def test_resampled_time_step(self):
        self.assertTrue(np.all(self.resampled.time[1:] - self.resampled.time[0:-1] == np.timedelta64(10, 's')))

    def test_resampled_values_length(self):
        self.assertEqual(len(self.resampled.values), 6)

    def test_resampled_values(self):
        self.assertTrue(np.all(self.resampled.values == np.arange(0., 60., 10.).reshape(-1, 1)))


class TestUpSamplingSimpleSlope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = datetime(2000, 1, 1, 1, 1)
        cls.stop = datetime(2000, 1, 1, 1, 2)
        cls.data = SpeasyVariable(
            axes=[VariableTimeAxis(values=generate_time_vector(cls.start, cls.stop, 1))],
            values=DataContainer(np.arange(60.).reshape(-1, 1))
        )
        cls.resampled = resample(cls.data, .5)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_resampled_length(self):
        self.assertEqual(len(self.resampled.time), len(self.data.time) * 2 - 1)

    def test_resampled_time_step(self):
        self.assertTrue(np.all((self.resampled.time[1:] - self.resampled.time[0:-1]) == np.timedelta64(500, 'ms')))

    def test_resampled_values_length(self):
        self.assertEqual(len(self.resampled.values), len(self.data.time) * 2 - 1)

    def test_resampled_values(self):
        self.assertTrue(np.allclose(self.resampled.values, np.arange(0., 59.5, .5).reshape(-1, 1)))


class TestUpSamplingSine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = datetime(2000, 1, 1, 1, 1)
        cls.stop = datetime(2000, 1, 1, 1, 2)
        cls.data = SpeasyVariable(
            axes=[VariableTimeAxis(values=generate_time_vector(cls.start, cls.stop, np.timedelta64(1, 'ms')))],
            values=DataContainer(np.sin(np.arange(0., 2 * np.pi, 2 * np.pi / 60000)).reshape(-1, 1))
        )
        cls.resampled = resample(cls.data, np.timedelta64(500, 'us'))

    @classmethod
    def tearDownClass(cls):
        pass

    def test_resampled_length(self):
        self.assertEqual(len(self.resampled.time), len(self.data.time) * 2 - 1)

    def test_resampled_time_step(self):
        self.assertTrue(np.all((self.resampled.time[1:] - self.resampled.time[0:-1]) == np.timedelta64(500, 'us')))

    def test_resampled_values_length(self):
        self.assertEqual(len(self.resampled.values), len(self.data.time) * 2 - 1)

    def test_resampled_values(self):
        self.assertTrue(np.allclose(self.resampled.values,
                                    np.sin(np.arange(0., 2 * np.pi, 2 * np.pi / (60000 * 2)))[:-1].reshape(-1, 1),
                                    rtol=3e-5))


class TestInterpolateVariableOverAnotherVariable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = datetime(2000, 1, 1, 1, 1)
        cls.stop = datetime(2000, 1, 1, 1, 2)
        cls.data = SpeasyVariable(
            axes=[VariableTimeAxis(values=generate_time_vector(cls.start, cls.stop, 1))],
            values=DataContainer(np.arange(60.).reshape(-1, 1))
        )
        cls.ref_var = SpeasyVariable(
            axes=[VariableTimeAxis(values=generate_time_vector(cls.start, cls.stop, 2))],
            values=DataContainer(np.arange(30.).reshape(-1, 1))
        )
        cls.resampled = interpolate(cls.data, cls.ref_var)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_resampled_length(self):
        self.assertEqual(len(self.resampled.time), len(self.ref_var.time))

    def test_resampled_values_length(self):
        self.assertEqual(len(self.resampled.values), len(self.ref_var.time))

    def test_resampled_values(self):
        self.assertTrue(np.all(self.resampled.values == np.arange(0., 60., 2.).reshape(-1, 1)))


class TestScipyInterpolator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = datetime(2000, 1, 1, 1, 1)
        cls.stop = datetime(2000, 1, 1, 1, 2)
        cls.data = SpeasyVariable(
            axes=[VariableTimeAxis(values=generate_time_vector(cls.start, cls.stop, np.timedelta64(1, 'ms')))],
            values=DataContainer(np.sin(np.arange(0., 2 * np.pi, 2 * np.pi / 60000)).reshape(-1, 1))
        )
        cls.resampled = resample(cls.data, np.timedelta64(500, 'us'),
                                 interpolate_callback=InterpolatedUnivariateSpline, k=4)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_resampled_length(self):
        self.assertEqual(len(self.resampled.time), len(self.data.time) * 2 - 1)

    def test_resampled_time_step(self):
        self.assertTrue(np.all((self.resampled.time[1:] - self.resampled.time[0:-1]) == np.timedelta64(500, 'us')))

    def test_resampled_values_length(self):
        self.assertEqual(len(self.resampled.values), len(self.data.time) * 2 - 1)

    def test_resampled_values(self):
        self.assertTrue(np.allclose(self.resampled.values,
                                    np.sin(np.arange(0., 2 * np.pi, 2 * np.pi / (60000 * 2)))[:-1].reshape(-1, 1),
                                    rtol=4e-5))
