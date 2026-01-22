#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `view3d` package."""
import unittest
from ddt import ddt

from speasy.data_providers import cdpp3dview


@ddt
class SscWeb(unittest.TestCase):
    def setUp(self):
        self.ssc = cdpp3dview.Cdpp3dViewWebservice()

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
