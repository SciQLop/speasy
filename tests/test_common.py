#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.common` package."""
import unittest

from ddt import ddt, data, unpack

import speasy as spz


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
        self.assertEqual(spz.core.listify(input), expected)


class Indexes(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_parameter_index_contains_component(self):
        self.assertIn(spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm.imf_gsm0,
                      spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm)

        self.assertNotIn(spz.inventories.tree.amda.Parameters.ACE.MFI.ace_mag_real.imf_real_gse.imf_real_gse1,
                         spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm)

        self.assertNotIn("random name that is not a component",
                         spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm)

    def test_dataset_index_contains_parameter(self):
        self.assertIn(spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all.imf_gsm,
                      spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all)

        self.assertNotIn(spz.inventories.tree.amda.Parameters.ACE.MFI.ace_mag_real.imf_real_gse,
                         spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all)

        self.assertNotIn("random name that is not a parameter",
                         spz.inventories.tree.amda.Parameters.ACE.MFI.ace_imf_all)


if __name__ == '__main__':
    unittest.main()
