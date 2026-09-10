import unittest
from datetime import datetime, timezone

import numpy as np

import speasy as spz
from speasy.core.time import make_utc_datetime64
from speasy.products.variable import (DataContainer, SpeasyVariable,
                                      VariableTimeAxis)
from speasy.virtual_products import registry

_START = datetime(2016, 10, 10, tzinfo=timezone.utc)
_STOP = datetime(2016, 10, 11, tzinfo=timezone.utc)


def _hourly_ramp(start_time, stop_time):
    """Stands in for a user callback: one point per hour over the requested window."""
    time = np.arange(make_utc_datetime64(start_time), make_utc_datetime64(stop_time),
                     np.timedelta64(1, 'h'))
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                          values=DataContainer(values=np.arange(len(time), dtype=float), meta=None),
                          columns=["Values"])


class VirtualProviderRegistration(unittest.TestCase):
    def test_virtual_provider_is_registered(self):
        self.assertIn("virtual", spz.list_providers())


class VirtualProductGetData(unittest.TestCase):
    def setUp(self):
        registry._register("test/dummy", _hourly_ramp)
        self.addCleanup(registry._callbacks.pop, "test/dummy", None)

    def test_get_data_returns_product(self):
        var = spz.get_data("virtual/test/dummy", _START, _STOP)
        self.assertIsInstance(var, SpeasyVariable)
        self.assertGreater(len(var), 0)

    def test_values_inside_time_window(self):
        var = spz.get_data("virtual/test/dummy", _START, _STOP)
        self.assertGreaterEqual(var.time[0], make_utc_datetime64(_START))
        self.assertLessEqual(var.time[-1], make_utc_datetime64(_STOP))


if __name__ == '__main__':
    unittest.main()
