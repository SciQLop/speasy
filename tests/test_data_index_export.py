import io
import os
import pickle
import tarfile
import tempfile
import unittest
from datetime import datetime, timezone

import numpy as np

from speasy.core import epoch_to_datetime64
from speasy.data_index import DataIndex
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis

_DAY = datetime(2023, 1, 1, tzinfo=timezone.utc)
_OPTIONS = {'coordinate_system': 'gse'}


def _variable(n=24, value=1.):
    index = _DAY.timestamp() + np.arange(n) * (86400. / n)
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
                          values=DataContainer(values=np.random.default_rng(0).normal(size=(n, 3)) + value))


def _folder():
    return os.path.join(tempfile.mkdtemp(), 'index')


class _Unpickled:
    """Records that it was unpickled: an archive must never be."""
    ran = False

    def __reduce__(self):
        return _mark_unpickled, ()


def _mark_unpickled():
    _Unpickled.ran = True


class ExportImport(unittest.TestCase):
    def setUp(self):
        self.source = DataIndex(_folder())
        self.addCleanup(self.source.close)
        self.tar = os.path.join(tempfile.mkdtemp(), 'study.tar')

    def _imported(self):
        target = DataIndex(_folder())
        self.addCleanup(target.close)
        target.import_data(self.tar)
        return target

    def test_a_round_trip_keeps_every_fragment_even_large_ones(self):
        # pysciqlop-cache stores large values as files next to its database: the export must carry them
        big = _variable(n=400_000)
        self.source.write_fragment('ssc/ace', _OPTIONS, _DAY, big, fetched_at=10)
        self.source.write_fragment('cda/AC_H0_MFI/BGSEc', {}, _DAY, None, fetched_at=10)
        self.source.export_data(self.tar)
        target = self._imported()
        np.testing.assert_array_equal(target.read_fragment('ssc/ace', _OPTIONS, _DAY).product.values, big.values)
        self.assertIsNone(target.read_fragment('cda/AC_H0_MFI/BGSEc', {}, _DAY).product)
        self.assertEqual(len(target.requests()), 2)

    def test_the_archive_holds_no_sqlite_side_files(self):
        self.source.write_fragment('ssc/ace', _OPTIONS, _DAY, _variable(), fetched_at=10)
        self.source.export_data(self.tar)
        with tarfile.open(self.tar) as tar:
            names = tar.getnames()
        self.assertFalse([n for n in names if n.endswith(('-wal', '-shm'))], names)

    def test_the_newer_fragment_wins_both_ways(self):
        self.source.write_fragment('ssc/ace', _OPTIONS, _DAY, _variable(value=1.), fetched_at=10)
        self.source.write_fragment('ssc/ace', _OPTIONS, _DAY.replace(day=2), _variable(value=1.), fetched_at=10)
        self.source.export_data(self.tar)
        target = DataIndex(_folder())
        self.addCleanup(target.close)
        target.write_fragment('ssc/ace', _OPTIONS, _DAY, _variable(value=2.), fetched_at=20)            # newer here
        target.write_fragment('ssc/ace', _OPTIONS, _DAY.replace(day=2), _variable(value=2.), fetched_at=5)  # older
        target.import_data(self.tar)
        self.assertEqual(target.read_fragment('ssc/ace', _OPTIONS, _DAY).fetched_at, 20)
        self.assertEqual(target.read_fragment('ssc/ace', _OPTIONS, _DAY.replace(day=2)).fetched_at, 10)

    def test_an_index_folder_imports_too(self):
        self.source.write_fragment('ssc/ace', _OPTIONS, _DAY, _variable(), fetched_at=10)
        self.source.close()
        target = DataIndex(_folder())
        self.addCleanup(target.close)
        target.import_data(self.source.path)
        self.assertIsNotNone(target.read_fragment('ssc/ace', _OPTIONS, _DAY))


class RefusedImports(unittest.TestCase):
    def setUp(self):
        self.target = DataIndex(_folder())
        self.addCleanup(self.target.close)

    def _tar_of(self, folder):
        tar_path = os.path.join(tempfile.mkdtemp(), 'archive.tar')
        with tarfile.open(tar_path, 'w') as tar:
            tar.add(folder, arcname='index')
        return tar_path

    def test_a_pickle_store_is_refused_without_being_unpickled(self):
        import pysciqlop_cache
        folder = _folder()
        store = pysciqlop_cache.Index(folder)
        store['__meta__'] = {'format': 1, 'fragment_hours': 24}
        store['data/ssc/ace/x/2023-01-01T00:00:00Z'] = _Unpickled()
        store.close()
        archive = self._tar_of(folder)
        with self.assertRaisesRegex(ValueError, "not a Speasy data index"):
            self.target.import_data(archive)
        self.assertFalse(_Unpickled.ran)

    def test_another_fragment_length_is_refused(self):
        import pysciqlop_cache
        from speasy.data_index._storable import Serializer
        source = DataIndex(_folder())
        source.close()
        store = pysciqlop_cache.Index(source.path, serializer=Serializer())
        store['__meta__'] = {**store['__meta__'], 'fragment_hours': 12}
        store.close()
        with self.assertRaisesRegex(ValueError, "12 h fragments.*24 h"):
            self.target.import_data(source.path)

    def test_a_folder_that_isnt_an_index_is_refused(self):
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, 'notes.txt'), 'w') as f:
            f.write('hello')
        with self.assertRaisesRegex(ValueError, "not a Speasy data index"):
            self.target.import_data(folder)

    def test_an_archive_writing_outside_its_folder_is_refused(self):
        tar_path = os.path.join(tempfile.mkdtemp(), 'evil.tar')
        with tarfile.open(tar_path, 'w') as tar:
            info = tarfile.TarInfo('../escaped.txt')
            data = b'x'
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, "escaped.txt"):
            self.target.import_data(tar_path)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(tar_path), 'escaped.txt')))


if __name__ == '__main__':
    unittest.main()
