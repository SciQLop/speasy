#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.common` package."""
import unittest
from ddt import ddt, data, unpack

import speasy.core


@ddt
class Listify(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        ("some text", ["some text"]),
        ([1], [1]),
        ((1, 2), [1, 2])
    )
    @unpack
    def test_listify(self, input, expected):
        self.assertEqual(speasy.core.listify(input), expected)
