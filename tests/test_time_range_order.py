import unittest

import numpy as np

import speasy as spz
from speasy.core.dataprovider import ParameterRangeCheck
from speasy.core.datetime_range import DateTimeRange
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis
from speasy.virtual_products import register_virtual_product


class _Provider:
    def parameter_range(self, product):
        return DateTimeRange("2000-01-01", "2030-01-01")

    @ParameterRangeCheck()
    def get_data(self, product, start_time, stop_time):
        return "data"


class StartAfterStop(unittest.TestCase):
    def test_provider_call_says_to_swap_the_dates(self):
        provider = _Provider()
        with self.assertRaisesRegex(ValueError, r"start .*2020-01-02.* is after stop .*2020-01-01.*swap"):
            provider.get_data("p", "2020-01-02", "2020-01-01")

    def test_get_data_says_to_swap_the_dates(self):
        register_virtual_product("virtual/test/time_order", lambda start, stop: None)
        with self.assertRaisesRegex(ValueError, r"start .*2020-01-02.* is after stop .*2020-01-01.*swap"):
            spz.get_data("virtual/test/time_order", "2020-01-02", "2020-01-01")

    def test_equal_dates_are_fine(self):
        self.assertEqual(_Provider().get_data("p", "2020-01-01", "2020-01-01"), "data")


def _variable(times):
    times = np.array(times, dtype="datetime64[ns]")
    return SpeasyVariable(axes=[VariableTimeAxis(values=times)], values=DataContainer(np.arange(len(times), dtype=float)))


class UnsortedTimeAxis(unittest.TestCase):
    def test_get_data_warns_when_the_source_data_is_not_sorted(self):
        register_virtual_product("virtual/test/unsorted",
                                 lambda start, stop: _variable(["2020-01-01T00:00", "2020-01-01T00:02", "2020-01-01T00:01"]))
        with self.assertWarnsRegex(UserWarning, r"virtual/test/unsorted.*time axis is not sorted"):
            spz.get_data("virtual/test/unsorted", "2020-01-01", "2020-01-02")

    def test_no_warning_when_sorted(self):
        import warnings
        register_virtual_product("virtual/test/sorted", lambda start, stop: _variable(["2020-01-01T00:00", "2020-01-01T00:01"]))
        with warnings.catch_warnings():
            warnings.filterwarnings("error", message=".*not sorted")
            spz.get_data("virtual/test/sorted", "2020-01-01", "2020-01-02")


if __name__ == '__main__':
    unittest.main()
