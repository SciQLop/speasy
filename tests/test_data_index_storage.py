import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import msgspec
import numpy as np

from speasy.core.codecs import get_codec
from speasy.data_index import DataIndex
from speasy.data_index._keys import data_key, fragments, options_hash, runs
from speasy.data_index._storable import Serializer, from_storable, to_storable
from speasy.products.variable import SpeasyVariable, from_dictionary

__HERE__ = os.path.dirname(os.path.abspath(__file__))


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _cdf_variable() -> SpeasyVariable:
    return get_codec('application/x-cdf').load_variable(
        'BGSEc', file=os.path.join(__HERE__, 'resources', 'ac_k2_mfi_20220101_v03.cdf'))


class Storable(unittest.TestCase):
    def test_a_real_cdf_variable_round_trips_through_the_serializer(self):
        # the meta of a real ISTP file, not only synthetic data
        variable = _cdf_variable()
        stored = Serializer().loads(Serializer().dumps(to_storable(variable.to_dictionary())))
        restored = from_dictionary(from_storable(stored))
        np.testing.assert_array_equal(restored.values, variable.values)
        np.testing.assert_array_equal(restored.time, variable.time)
        self.assertEqual(restored.columns, variable.columns)
        self.assertEqual(restored.meta, variable.meta)
        np.testing.assert_array_equal(restored.axes[1].values, variable.axes[1].values)   # a bytes label axis

    def test_arrays_blosc_leaves_alone_keep_their_dtype(self):
        for array in (np.array([], dtype='f4'), np.array(['ab', 'c']), np.array([b'x', b'yz'])):
            with self.subTest(dtype=array.dtype):
                restored = from_storable(Serializer().loads(Serializer().dumps(to_storable({'a': array}))))['a']
                self.assertEqual(restored.dtype, array.dtype)
                np.testing.assert_array_equal(restored, array)

    def test_meta_becomes_plain_data_and_keeps_its_types(self):
        meta = {'n': np.int32(3), 'x': np.float64(1.5), 'b': np.bool_(True), 'when': datetime(2020, 1, 1),
                'np_when': np.datetime64('2020-01-01T00:00:00'), 'pair': (1, 2), 3: 'int key'}
        self.assertEqual(from_storable(Serializer().loads(Serializer().dumps(to_storable(meta)))),
                         {'n': 3, 'x': 1.5, 'b': True, 'when': datetime(2020, 1, 1),
                          'np_when': np.datetime64('2020-01-01T00:00:00'), 'pair': (1, 2), '3': 'int key'})

    def test_an_object_array_of_something_unstorable_is_refused_with_its_field(self):
        from speasy.data_index._storable import NotStorable
        with self.assertRaisesRegex(NotStorable, r"values/meta/LABELS.*object"):
            to_storable({'values': {'meta': {'LABELS': np.array([object()])}}})


class NoExtensionSerializer(unittest.TestCase):
    def test_refuses_anything_that_is_not_plain_data_on_write(self):
        # datetimes are plain msgpack (its timestamp type), no class is involved
        for value in (np.arange(3), np.int32(1), object()):
            with self.subTest(value=type(value).__name__), self.assertRaises(TypeError):
                Serializer().dumps({'v': value})

    def test_never_builds_an_object_on_read(self):
        # pysciqlop-cache's msgspec serializer imports the class an "object" extension names
        hostile = msgspec.msgpack.encode(msgspec.msgpack.Ext(2, b'os.system'))
        self.assertIsInstance(Serializer().loads(hostile), msgspec.msgpack.Ext)


class Fragments(unittest.TestCase):
    _NOW = _utc(2026, 10, 23, 12)

    def test_a_midnight_to_midnight_day_is_one_fragment(self):
        self.assertEqual(fragments(_utc(2023, 1, 1), _utc(2023, 1, 2), now=self._NOW), [_utc(2023, 1, 1)])

    def test_an_unaligned_day_is_two_fragments(self):
        self.assertEqual(fragments(_utc(2023, 1, 1, 10), _utc(2023, 1, 2, 10), now=self._NOW),
                         [_utc(2023, 1, 1), _utc(2023, 1, 2)])

    def test_any_spelling_of_an_instant_gives_the_same_fragments(self):
        expected = fragments(_utc(2023, 1, 1), _utc(2023, 1, 3), now=self._NOW)
        for start, stop in (("2023-01-01T00:00:00Z", "2023-01-03T00:00:00+00:00"),
                            ("2023-01-01T02:00:00+02:00", "2023-01-03"),
                            (np.datetime64('2023-01-01'), np.datetime64('2023-01-03'))):
            with self.subTest(start=start):
                self.assertEqual(fragments(start, stop, now=self._NOW), expected)

    def test_the_future_is_never_part_of_the_grid(self):
        self.assertEqual(fragments(self._NOW - timedelta(days=1), self._NOW + timedelta(days=365), now=self._NOW),
                         [_utc(2026, 10, 22), _utc(2026, 10, 23)])

    def test_runs_are_consecutive_fragments(self):
        day = timedelta(days=1)
        start = _utc(2023, 1, 1)
        self.assertEqual(runs([start, start + day, start + 3 * day, start + 4 * day, start + 6 * day]),
                         [[start, start + day], [start + 3 * day, start + 4 * day], [start + 6 * day]])


class Keys(unittest.TestCase):
    def test_the_options_hash_ignores_dict_order(self):
        self.assertEqual(options_hash({'a': 1, 'product_inputs': {'x': 1, 'y': 2}}),
                         options_hash({'product_inputs': {'y': 2, 'x': 1}, 'a': 1}))

    def test_aliases_and_slashes(self):
        key = data_key('cdaweb', 'AC_H0_MFI/BGSEc', 'abcd', _utc(2023, 1, 1))
        self.assertEqual(key, data_key('cda', 'AC_H0_MFI/BGSEc', 'abcd', _utc(2023, 1, 1)))
        self.assertEqual(key, 'data/cda/AC_H0_MFI%2FBGSEc/abcd/2023-01-01T00:00:00Z')


class PublicName(unittest.TestCase):
    def test_spz_data_index_is_loaded_on_first_use(self):
        # import speasy must keep working where DataIndex can't (Pyodide has no pysciqlop-cache)
        import subprocess
        import sys
        code = ("import sys, speasy; assert 'speasy.data_index' not in sys.modules; "
                "from speasy.data_index import DataIndex; assert speasy.DataIndex is DataIndex")
        subprocess.run([sys.executable, "-c", code], check=True, env={**os.environ, "SPEASY_SKIP_INIT_PROVIDERS": "1"})


class Opening(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mkdtemp()

    def test_an_empty_folder_becomes_an_index_and_reopens(self):
        DataIndex(self.path).close()
        DataIndex(self.path).close()

    def test_a_folder_holding_something_else_is_refused(self):
        with open(os.path.join(self.path, 'notes.txt'), 'w') as f:
            f.write('my study')
        with self.assertRaisesRegex(ValueError, r"not a Speasy data index"):
            DataIndex(self.path)

    def test_a_pickle_store_is_refused_without_being_read(self):
        import pysciqlop_cache
        store = pysciqlop_cache.Index(self.path)
        store['__meta__'] = {'format': 1}
        store.close()
        with self.assertRaisesRegex(ValueError, r"pickle"):
            DataIndex(self.path)

    def test_an_unknown_format_says_which_speasy_to_use(self):
        DataIndex(self.path).close()
        import pysciqlop_cache
        store = pysciqlop_cache.Index(self.path, serializer=Serializer())
        store['__meta__'] = {**store['__meta__'], 'format': 99}
        store.close()
        with self.assertRaisesRegex(ValueError, r"format 99.*newer Speasy"):
            DataIndex(self.path)


class Entries(unittest.TestCase):
    def setUp(self):
        self.index = DataIndex(tempfile.mkdtemp())
        self.addCleanup(self.index.close)

    def test_a_fragment_round_trips(self):
        variable = _cdf_variable()
        self.index.write_fragment('cda/AC_K2_MFI/BGSEc', {}, _utc(2022, 1, 1), variable, fetched_at=1_700_000_000)
        entry = self.index.read_fragment('cda/AC_K2_MFI/BGSEc', {}, _utc(2022, 1, 1))
        self.assertEqual(entry.fetched_at, 1_700_000_000)
        np.testing.assert_array_equal(entry.product.values, variable.values)

    def test_an_empty_fragment_is_not_a_missing_one(self):
        self.index.write_fragment('cda/AC_K2_MFI/BGSEc', {}, _utc(2022, 1, 1), None, fetched_at=1)
        self.assertIsNone(self.index.read_fragment('cda/AC_K2_MFI/BGSEc', {}, _utc(2022, 1, 1)).product)
        self.assertIsNone(self.index.read_fragment('cda/AC_K2_MFI/BGSEc', {}, _utc(2022, 1, 2)))

    def test_options_select_their_own_entries(self):
        self.index.write_fragment('ssc/ace', {'coordinate_system': 'gse'}, _utc(2022, 1, 1), None, fetched_at=1)
        self.assertIsNone(self.index.read_fragment('ssc/ace', {'coordinate_system': 'geo'}, _utc(2022, 1, 1)))

    def test_every_stored_request_is_listed(self):
        self.index.write_fragment('sscweb/ace', {'coordinate_system': 'gse'}, _utc(2022, 1, 1), None, fetched_at=1)
        self.index.write_fragment('ssc/ace', {'coordinate_system': 'gse'}, _utc(2022, 1, 2), None, fetched_at=1)
        self.assertEqual(self.index.requests(),
                         [{'provider': 'ssc', 'product': 'ace', 'options': {'coordinate_system': 'gse'}}])


if __name__ == '__main__':
    unittest.main()
