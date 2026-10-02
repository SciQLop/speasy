import sys
import threading
import unittest
from unittest.mock import patch

import speasy as spz
from speasy.core import dataprovider as dp
from speasy.core.dataprovider import DataProvider, register_provider


def _provider_class(name, alt_names=()):
    return type(f"Fake_{name}", (), {"NAME": name, "ALIASES": tuple(alt_names)})


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
        clashing = _provider_class("other", ["cdaweb"])
        with self.assertRaises(ValueError):
            register_provider(clashing)
        self.assertEqual(dp.registered_providers(), {"cda": existing})
        self.assertIsNone(dp.main_provider_name("other"))

    def test_a_class_without_provider_name_is_rejected(self):
        nameless = _provider_class(None)
        with self.assertRaises(ValueError):
            register_provider(nameless)

    def test_a_mixed_case_main_name_is_rejected(self):
        # get_data lowercases the provider of an index, so a mixed-case main name could never be routed
        mixed_case = _provider_class("MyProv")
        with self.assertRaises(ValueError):
            register_provider(mixed_case)
        self.assertEqual(dp.registered_providers(), {})

    def test_a_string_instead_of_a_tuple_of_alternative_names_is_rejected(self):
        # ('cdaweb') is a str, not a tuple: without the guard every letter would become an alias
        missing_comma = type("MissingComma", (), {"NAME": "cda", "ALIASES": ("cdaweb")})
        with self.assertRaises(TypeError):
            register_provider(missing_comma)
        self.assertEqual(dp.registered_providers(), {})

    def test_mixed_case_alternative_names_are_accepted(self):
        cls = register_provider(_provider_class("uiowaephtool", ["UiowaEphTool"]))
        self.assertEqual(dp.main_provider_name("UiowaEphTool"), "uiowaephtool")
        self.assertIs(dp.registered_providers()["uiowaephtool"], cls)


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
            NAME = "declared"
            ALIASES = ("decl",)

        provider = Declared()
        self.assertEqual((provider.provider_name, provider.provider_alt_names), ("declared", ["decl"]))
        self.assertIs(dp.flat_inventories.__dict__["decl"], provider.flat_inventory)

    def test_passing_the_declared_name_again_is_accepted(self):
        class Declared(DataProvider):
            NAME = "declared"

            def __init__(self):
                DataProvider.__init__(self, provider_name=self.NAME)

        self.assertEqual(Declared().provider_name, "declared")

    def test_a_name_conflicting_with_the_class_attributes_raises(self):
        class OtherName(DataProvider):
            NAME = "declared"

            def __init__(self):
                DataProvider.__init__(self, provider_name="other")

        class OtherAltNames(DataProvider):
            NAME = "declared"

            def __init__(self):
                DataProvider.__init__(self, provider_alt_names=["other"])

        for cls in (OtherName, OtherAltNames):
            with self.subTest(cls.__name__), self.assertRaises(ValueError):
                cls()

    def test_a_string_of_alternative_names_is_rejected(self):
        class MissingComma(DataProvider):
            NAME = "declared"
            ALIASES = ("decl")

        class OldStyleString(DataProvider):
            def __init__(self):
                DataProvider.__init__(self, "oldstyle", "old")

        for cls in (MissingComma, OldStyleString):
            with self.subTest(cls.__name__), self.assertRaises(TypeError):
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
            NAME = "base"

        class Tweaked(Base):
            pass

        self.assertEqual(Tweaked().provider_name, "base")
        self.assertIs(dp.registered_providers()["base"], Base)


class RegistrationErrorMessages(_IsolatedRegistry):
    # Plugin authors only see these messages, often as a logged warning: each must say how to fix the class
    def test_a_missing_name_says_how_to_set_it(self):
        class MyProvider(DataProvider):
            pass

        with self.assertRaisesRegex(ValueError, r"MyProvider.*set a NAME class attribute, e\.g\. NAME = 'myprovider'"):
            register_provider(MyProvider)

    def test_an_inherited_name_says_where_it_comes_from(self):
        @register_provider
        class Base(DataProvider):
            NAME = "base"

        class Tweaked(Base):
            pass

        with self.assertRaisesRegex(ValueError, r"Tweaked inherits NAME 'base' from Base.*give it its own NAME"):
            register_provider(Tweaked)

    def test_a_forgotten_decorator_is_pointed_out_when_the_provider_is_not_found(self):
        class Forgotten(DataProvider):
            NAME = "forgotten"

        # never referenced directly: the hint finds it through DataProvider's subclasses
        with self.assertRaisesRegex(ValueError, rf"{Forgotten.__name__} declares NAME '{Forgotten.NAME}' "
                                                r"but is not decorated with @register_provider"):
            spz.get_data("forgotten/x", "2020-01-01", "2020-01-02")

    def test_an_unknown_provider_gets_no_decorator_hint(self):
        with self.assertRaises(ValueError) as raised:
            spz.get_data("nosuchprovider/x", "2020-01-01", "2020-01-02")
        self.assertNotIn("register_provider", str(raised.exception))


class RegistryThreadSafety(_IsolatedRegistry):
    # A tiny switch interval makes the interpreter interleave threads between almost every bytecode,
    # so a race in the registry shows up in a few thousand iterations instead of once in a blue moon.
    def setUp(self):
        super().setUp()
        previous = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        self.addCleanup(sys.setswitchinterval, previous)

    def test_listing_providers_while_another_thread_registers_never_fails(self):
        stop, errors = threading.Event(), []

        def list_continuously():
            while not stop.is_set():
                try:
                    dp.registered_providers()
                except RuntimeError as error:
                    errors.append(error)
                    return

        reader = threading.Thread(target=list_continuously)
        reader.start()
        for i in range(3000):
            register_provider(_provider_class(f"p{i}"))
        stop.set()
        reader.join(10)
        self.assertEqual(errors, [])

    def test_concurrent_registrations_of_one_name_let_exactly_one_win(self):
        for round_ in range(300):
            dp._PROVIDER_CLASSES.clear()
            candidates = [_provider_class("same") for _ in range(8)]
            start, winners, rejected = threading.Barrier(len(candidates)), [], []

            def register(cls):
                start.wait()
                try:
                    winners.append(register_provider(cls))
                except ValueError as error:
                    rejected.append(error)

            threads = [threading.Thread(target=register, args=(cls,)) for cls in candidates]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(10)
            with self.subTest(round=round_):
                self.assertEqual((len(winners), len(rejected)), (1, len(candidates) - 1))
                self.assertEqual(dp.registered_providers(), {"same": winners[0]})


if __name__ == "__main__":
    unittest.main()
