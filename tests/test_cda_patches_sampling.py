import os
import random
import unittest
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import speasy as spz
from ddt import ddt, data

from speasy.core.direct_archive_downloader.direct_archive_downloader import first_file
from speasy.data_providers.cda._direct_archive import to_direct_archive_params
from speasy.data_providers.cda._patches.reader import patched_reader, _load
from speasy.data_providers.cda._patches.table import PATCHES

DATASETS = tuple(dict.fromkeys(p.dataset for p in PATCHES))
ATTEMPTS = 20
SEED = int(os.environ.get('SPEASY_SAMPLING_SEED', random.SystemRandom().randrange(2 ** 32)))


def _random_day(dataset, rng: random.Random) -> datetime:
    start, stop = (datetime.fromisoformat(d).replace(tzinfo=None) for d in (dataset.start_date, dataset.stop_date))
    return (start + (stop - start) * rng.random()).replace(hour=0, minute=0, second=0, microsecond=0)


def _file_on_a_random_day(dataset, rng: random.Random) -> Optional[str]:
    params = to_direct_archive_params(file_naming=dataset.filenaming, subdivided_by=dataset.subdividedby,
                                      url=dataset.url)
    days = (_random_day(dataset, rng) for _ in range(ATTEMPTS))
    urls = (first_file(start_time=day, stop_time=day + timedelta(days=1), **params) for day in days)
    return next(filter(None, urls), None)


def _first_index_in(decoded, var) -> int:
    """Index in the decoded file of the first sample of `var`, which must be the very same sample (time and values):
    a web service fallback would not return the file's flat samples. The request start is rounded to microseconds,
    so the first sample may be a few samples after the requested one. The request starts in the middle of the file:
    a file can start in the previous day (SolO TSWF), where the archive looks for another file."""
    index = int(np.searchsorted(decoded.time, var.time[0]))
    np.testing.assert_array_equal(decoded.time[index], var.time[0])
    np.testing.assert_array_equal(decoded.values[index], var.values[0])
    return index


@unittest.skipUnless(os.environ.get('SPEASY_LONG_TESTS'), "downloads one file per patched dataset, some over 100 MB")
@ddt
class EveryPatchOnARandomFile(unittest.TestCase):
    @data(*DATASETS)
    def test_every_patch_on_a_random_file(self, dataset_id):
        dataset = spz.inventories.flat_inventories.cda.datasets[dataset_id]
        url = _file_on_a_random_day(dataset, random.Random(f'{SEED}/{dataset_id}'))
        if url is None:
            self.fail(f"seed {SEED}: no file of {dataset_id} found in {ATTEMPTS} random days")
        for entry in (p for p in PATCHES if p.dataset == dataset_id):
            with self.subTest(product=entry.name):
                msg = f"seed {SEED}, file {url}, product {entry.name}"
                decoded = patched_reader(entry)(url, entry.variable)
                if decoded is None and _load(url)[entry.variable].shape[0] == 0:
                    self.skipTest(f"{url} holds no record of {entry.variable}")
                self.assertIsNotNone(decoded, msg)
                start_index = len(decoded) // 2
                start = decoded.time[start_index]
                var = spz.get_data(f'cda/{dataset_id}/{entry.name}', start, start + np.timedelta64(1, 'h'),
                                   method='FILE')
                self.assertIsNotNone(var, msg)
                self.assertEqual(var.time.ndim, 1, msg)
                self.assertEqual(len(var.time), var.values.shape[0], msg)
                self.assertGreater(len(var), 0, msg)
                self.assertLess(_first_index_in(decoded, var) - start_index, 100, msg)
                self.assertTrue(np.all(np.diff(var.time) > np.timedelta64(0, 'ns')), msg)


if __name__ == '__main__':
    unittest.main()
