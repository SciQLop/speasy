import unittest

import numpy as np
from ddt import data, ddt

from speasy.core.proxy import blosc_arrays, unblosc_arrays

_ARRAYS = {
    'float64': np.linspace(0, 1, 1000),
    'float32_2d': np.linspace(0, 1, 3000, dtype='float32').reshape(1000, 3),
    'int16': np.arange(1000, dtype='int16'),
    'uint8_3d': np.arange(24, dtype='uint8').reshape(2, 3, 4),
    'bool': np.arange(10) % 2 == 0,
    'complex': np.arange(10) * (1 + 2j),
    'datetime64': np.datetime64('2020-01-01', 'ns') + np.arange(100) * np.timedelta64(1, 's'),
    'timedelta64': np.arange(100) * np.timedelta64(1, 'ms'),
    'big_endian': np.arange(10, dtype='>f8'),
}


@ddt
class BloscArrays(unittest.TestCase):
    @data(*_ARRAYS)
    def test_round_trip(self, name):
        array = _ARRAYS[name]
        decoded = unblosc_arrays(blosc_arrays(array))
        self.assertEqual(decoded.dtype, array.dtype)
        self.assertEqual(decoded.shape, array.shape)
        np.testing.assert_array_equal(decoded, array)
        self.assertTrue(decoded.flags.writeable)

    @data(*_ARRAYS)
    def test_marker_holds_only_plain_types(self, name):
        # stored with msgpack by the data index (#122): no numpy dtype or tuple in the marker
        marker = blosc_arrays(_ARRAYS[name])
        self.assertEqual({k: type(v) for k, v in marker.items()},
                         {'__blosc__': bytes, 'dtype': str, 'shape': list})

    def test_nested_containers_keep_their_shape(self):
        obj = {'values': {'values': _ARRAYS['float64'], 'meta': {'UNITS': 'nT'}},
               'axes': [{'values': _ARRAYS['datetime64'], 'name': 'time'}], 'n': 3}
        decoded = unblosc_arrays(blosc_arrays(obj))
        np.testing.assert_array_equal(decoded['values']['values'], _ARRAYS['float64'])
        np.testing.assert_array_equal(decoded['axes'][0]['values'], _ARRAYS['datetime64'])
        self.assertEqual((decoded['values']['meta'], decoded['axes'][0]['name'], decoded['n']),
                         ({'UNITS': 'nT'}, 'time', 3))

    def test_arrays_blosc_cannot_hold_are_left_as_they_are(self):
        # blosc only takes numbers, and numcodecs can't decode the chunk it makes for an empty array
        for array in (np.array(['a', 'b']), np.array([], dtype='f8'), np.array([object()])):
            with self.subTest(dtype=array.dtype, size=array.size):
                self.assertIs(blosc_arrays(array), array)

    def test_compresses(self):
        marker = blosc_arrays(_ARRAYS['float32_2d'])
        self.assertLess(len(marker['__blosc__']), _ARRAYS['float32_2d'].nbytes)


if __name__ == '__main__':
    unittest.main()
