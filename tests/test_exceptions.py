"""speasy.core.exceptions: one base for speasy's errors, and one class for an id nothing knows."""
import importlib
import unittest

from ddt import data, ddt, unpack

import speasy as spz

START, STOP = "2020-01-01", "2020-01-01T01"


@ddt
class UnknownIdsRaiseUnknownProduct(unittest.TestCase):
    @data(
        ("amda/this_product_does_not_exist", "UnknownProduct"),
        ("cda/NOT_A_DATASET/not_a_variable", "UnknownProduct"),
        ("cda/no_slash_in_this_id", "UnknownProduct"),
        ("csa/NOT_A_DATASET/not_a_variable", "UnknownProduct"),
        ("csa/no_slash_in_this_id", "UnknownProduct"),
        ("ssc/not_a_spacecraft", "UnknownProduct"),
        ("cdpp3dview/not_a_body", "UnknownProduct"),
        ("uiowaephtool/not_a_trajectory", "UnknownProduct"),
        ("archive/not/a_product", "UnknownProduct"),
        ("hapi/not_a_server/dataset/parameter", "UnknownProduct"),
        ("virtual/not_a_virtual_product", "UnknownProduct"),
        ("not_a_provider/product", "UnknownProvider"),
        ("no_slash_at_all", "UnknownProduct"),
    )
    @unpack
    def test_get_data_on_an_unknown_id(self, product, expected):
        from speasy.core import exceptions
        with self.assertRaises(getattr(exceptions, expected)) as raised:
            spz.get_data(product, START, STOP)
        self.assertIsInstance(raised.exception, exceptions.UnknownProduct)
        self.assertIsInstance(raised.exception, ValueError)
        self.assertIsInstance(raised.exception, exceptions.SpeasyError)

    def test_an_unknown_dataset(self):
        from speasy.core.exceptions import UnknownDataset
        with self.assertRaisesRegex(UnknownDataset, "Unknown dataset: NOT_A_DATASET"):
            spz.cda.dataset_range("NOT_A_DATASET")

    def test_an_unknown_parameter(self):
        from speasy.core.exceptions import UnknownParameter
        with self.assertRaisesRegex(UnknownParameter, "Unknown parameter: not_a_spacecraft"):
            spz.ssc.parameter_range("not_a_spacecraft")

    def test_an_unknown_provider_by_name(self):
        from speasy.core.dataprovider import provider_class
        from speasy.core.exceptions import UnknownProvider
        with self.assertRaisesRegex(UnknownProvider, "Unknown provider 'not_a_provider'"):
            provider_class("not_a_provider")


    def test_an_unknown_csa_dataset_has_no_last_update(self):
        # it was a bare KeyError
        from speasy.core.exceptions import UnknownDataset
        with self.assertRaisesRegex(UnknownDataset, "Unknown dataset: NOT_A_DATASET"):
            spz.csa.product_last_update("NOT_A_DATASET/not_a_variable")

    def test_an_unknown_amda_product_has_no_parent_dataset(self):
        from speasy.core.exceptions import UnknownProduct
        with self.assertRaisesRegex(UnknownProduct, "Unknown product: this_product_does_not_exist"):
            spz.amda.find_parent_dataset("this_product_does_not_exist")

    def test_initializing_an_unknown_provider(self):
        from speasy.core.exceptions import UnknownProvider
        from speasy.core.requests_scheduling.request_dispatch import init_provider
        with self.assertRaisesRegex(UnknownProvider, "Unknown provider 'not_a_provider'"):
            init_provider("not_a_provider")

EXCEPTIONS = {
    "speasy.core.hapi.exceptions": ("HapiError", "HapiRequestError", "HapiServerError", "HapiNoData",
                                    "HapiServerUnavailable"),
    "speasy.core.impex.exceptions": ("MissingCredentials", "UnavailableEndpoint", "BadTemplateArgDefinition",
                                     "FailedChunkedRequest", "InvalidCredentials"),
    "speasy.core.proxy": ("ProxyError",),
    "speasy.core.tap": ("TapError",),
    "speasy.data_providers.cda": ("CdaWebException",),
    "speasy.data_providers.cdpp3dview": ("Cdpp3dViewWebException",),
    "speasy.core.virtual_products.expression": ("TimeAxisMismatch",),
    "speasy.virtual_products.registry": ("UnknownVirtualProduct", "VirtualProductTypeError",
                                         "VirtualProductCycleError"),
    "speasy.data_index._storable": ("NotStorable",),
}


@ddt
class PublicExceptions(unittest.TestCase):
    @data(*[(module, name) for module, names in EXCEPTIONS.items() for name in names])
    @unpack
    def test_old_import_path_gives_the_speasy_exceptions_class(self, module, name):
        from speasy.core import exceptions
        cls = getattr(importlib.import_module(module), name)
        self.assertIs(cls, getattr(exceptions, name))
        self.assertTrue(issubclass(cls, exceptions.SpeasyError))

    @data(("HapiServerUnavailable", ConnectionError), ("TimeAxisMismatch", ValueError),
          ("UnknownVirtualProduct", ValueError), ("VirtualProductTypeError", TypeError),
          ("VirtualProductCycleError", RecursionError), ("NotStorable", TypeError),
          ("UnknownProduct", ValueError))
    @unpack
    def test_extra_bases_are_kept(self, name, base):
        from speasy.core import exceptions
        self.assertTrue(issubclass(getattr(exceptions, name), base))

    def test_an_unknown_virtual_product_is_an_unknown_product(self):
        from speasy.core.exceptions import UnknownProduct, UnknownVirtualProduct
        self.assertTrue(issubclass(UnknownVirtualProduct, UnknownProduct))

    def test_extra_attributes_are_kept(self):
        from speasy.core.exceptions import HapiRequestError, NotStorable
        e = HapiRequestError(1406, "unknown dataset id")
        self.assertEqual((e.code, e.message, str(e)), (1406, "unknown dataset id", "unknown dataset id"))
        self.assertEqual(NotStorable("no", product="p").product, "p")


if __name__ == '__main__':
    unittest.main()
