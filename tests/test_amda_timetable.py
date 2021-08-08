#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package timetable implementation."""

import unittest
from speasy.amda import AMDA


class TimetableRequests(unittest.TestCase):
    def setUp(self):
        self.ws = AMDA()
        self.tt = self.ws.get_timetable("sharedtimeTable_0")

    def tearDown(self):
        pass

    def test_timetable_shape(self):
        self.assertTrue(len(self.tt) > 0)

    def test_timetable_has_a_name(self):
        self.assertIsNot(self.tt.name, "")


if __name__ == '__main__':
    unittest.main()
