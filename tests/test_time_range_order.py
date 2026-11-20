import unittest

import speasy as spz
from speasy.core.dataprovider import ParameterRangeCheck
from speasy.core.datetime_range import DateTimeRange
from speasy.virtual_products import register_virtual_product


class _Provider:
    def parameter_range(self, product):
        return DateTimeRange("2000-01-01", "2030-01-01")

    @ParameterRangeCheck()
    def get_data(self, product, start_time, stop_time):
        return "data"


class StartAfterStop(unittest.TestCase):
    def test_provider_call_says_to_swap_the_dates(self):
        with self.assertRaisesRegex(ValueError, r"start .*2020-01-02.* is after stop .*2020-01-01.*swap"):
            _Provider().get_data("p", "2020-01-02", "2020-01-01")

    def test_get_data_says_to_swap_the_dates(self):
        register_virtual_product("virtual/test/time_order", lambda start, stop: None)
        with self.assertRaisesRegex(ValueError, r"start .*2020-01-02.* is after stop .*2020-01-01.*swap"):
            spz.get_data("virtual/test/time_order", "2020-01-02", "2020-01-01")

    def test_equal_dates_are_fine(self):
        self.assertEqual(_Provider().get_data("p", "2020-01-01", "2020-01-01"), "data")


if __name__ == '__main__':
    unittest.main()
