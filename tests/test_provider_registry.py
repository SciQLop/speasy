import unittest
from unittest.mock import patch

from speasy.core import dataprovider as dp
from speasy.core.dataprovider import DataProvider, register_provider


def _provider_class(name, alt_names=()):
    return type(f"Fake_{name}", (), {"PROVIDER_NAME": name, "PROVIDER_ALT_NAMES": tuple(alt_names)})


class _IsolatedRegistry(unittest.TestCase):
    def setUp(self):
        registry = patch.dict(dp._PROVIDER_CLASSES, clear=True)
        registry.start()
        self.addCleanup(registry.stop)


class ProviderRegistry(_IsolatedRegistry):
    def test_registered_class_is_found_by_main_and_alternative_names(self):
        cls = register_provider(_provider_class("fake", ["fk", "FaKe"]))
        self.assertEqual(dp.registered_providers(), {"fake": cls})
        for name in ("fake", "fk", "FaKe"):
            self.assertEqual(dp.main_provider_name(name), "fake")
        self.assertEqual(dp.provider_names("fake"), ["fake", "fk", "FaKe"])
        self.assertIsNone(dp.main_provider_name("nope"))

    def test_registration_order_is_kept(self):
        for name in ("b", "a", "c"):
            register_provider(_provider_class(name))
        self.assertEqual(list(dp.registered_providers()), ["b", "a", "c"])

    def test_a_name_clash_raises_and_registers_nothing(self):
        existing = register_provider(_provider_class("cda", ["cdaweb"]))
        with self.assertRaises(ValueError):
            register_provider(_provider_class("other", ["cdaweb"]))
        self.assertEqual(dp.registered_providers(), {"cda": existing})
        self.assertIsNone(dp.main_provider_name("other"))

    def test_a_class_without_provider_name_is_rejected(self):
        with self.assertRaises(ValueError):
            register_provider(_provider_class(None))


class DataProviderNames(_IsolatedRegistry):
    # DataProvider.__init__ fetches the inventory; that part is not under test here
    def setUp(self):
        super().setUp()
        for patcher in (patch.object(DataProvider, "update_inventory"),
                        patch.dict(dp.PROVIDERS),
                        patch.dict(dp.flat_inventories.__dict__)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_names_come_from_class_attributes(self):
        class Declared(DataProvider):
            PROVIDER_NAME = "declared"
            PROVIDER_ALT_NAMES = ("decl",)

        provider = Declared()
        self.assertEqual((provider.provider_name, provider.provider_alt_names), ("declared", ["decl"]))
        self.assertIs(dp.flat_inventories.__dict__["decl"], provider.flat_inventory)

    def test_passing_the_declared_name_again_is_accepted(self):
        class Declared(DataProvider):
            PROVIDER_NAME = "declared"

            def __init__(self):
                DataProvider.__init__(self, provider_name=self.PROVIDER_NAME)

        self.assertEqual(Declared().provider_name, "declared")

    def test_a_name_conflicting_with_the_class_attributes_raises(self):
        class OtherName(DataProvider):
            PROVIDER_NAME = "declared"

            def __init__(self):
                DataProvider.__init__(self, provider_name="other")

        class OtherAltNames(DataProvider):
            PROVIDER_NAME = "declared"

            def __init__(self):
                DataProvider.__init__(self, provider_alt_names=["other"])

        for cls in (OtherName, OtherAltNames):
            with self.subTest(cls.__name__), self.assertRaises(ValueError):
                cls()

    def test_old_style_subclass_still_takes_names_as_arguments(self):
        class OldStyle(DataProvider):
            def __init__(self):
                DataProvider.__init__(self, "oldstyle", ["old"])

        provider = OldStyle()
        self.assertEqual((provider.provider_name, provider.provider_alt_names), ("oldstyle", ["old"]))
        self.assertEqual(dp.registered_providers(), {})

    def test_a_subclass_without_any_name_raises(self):
        class Nameless(DataProvider):
            pass

        with self.assertRaises(TypeError):
            Nameless()

    def test_subclassing_a_registered_provider_does_not_take_over_its_names(self):
        @register_provider
        class Base(DataProvider):
            PROVIDER_NAME = "base"

        class Tweaked(Base):
            pass

        self.assertEqual(Tweaked().provider_name, "base")
        self.assertIs(dp.registered_providers()["base"], Base)


if __name__ == "__main__":
    unittest.main()
