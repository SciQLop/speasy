import os
import random
import unittest
from datetime import datetime, timedelta

import numpy as np
import speasy as spz
from ddt import ddt, data

from speasy.core.direct_archive_downloader.direct_archive_downloader import first_file
from speasy.data_providers.cda._direct_archive import to_direct_archive_params
from speasy.data_providers.cda._patches.reader import patched_reader
from speasy.data_providers.cda._patches.table import PATCHES

DATASETS = tuple(dict.fromkeys(p.dataset for p in PATCHES))
ATTEMPTS = 20
SEED = int(os.environ.get('SPEASY_SAMPLING_SEED', random.SystemRandom().randrange(2 ** 32)))


def _random_day(dataset, rng: random.Random) -> datetime:
    start, stop = (datetime.fromisoformat(d).replace(tzinfo=None) for d in (dataset.start_date, dataset.stop_date))
    return (start + (stop - start) * rng.random()).replace(hour=0, minute=0, second=0, microsecond=0)


def _file_on_a_random_day(dataset, rng: random.Random) -> str:
    params = to_direct_archive_params(file_naming=dataset.filenaming, subdivided_by=dataset.subdividedby,
                                      url=dataset.url)
    days = (_random_day(dataset, rng) for _ in range(ATTEMPTS))
    urls = (first_file(start_time=day, stop_time=day + timedelta(days=1), **params) for day in days)
    return next(filter(None, urls))


@unittest.skipUnless(os.environ.get('SPEASY_LONG_TESTS'), "downloads one file per patched dataset, some over 100 MB")
@ddt
class EveryPatchOnARandomFile(unittest.TestCase):
    @data(*DATASETS)
    def test_every_patch_on_a_random_file(self, dataset_id):
        dataset = spz.inventories.flat_inventories.cda.datasets[dataset_id]
        url = _file_on_a_random_day(dataset, random.Random(f'{SEED}/{dataset_id}'))
        for entry in (p for p in PATCHES if p.dataset == dataset_id):
            with self.subTest(product=entry.name):
                msg = f"seed {SEED}, file {url}, product {entry.name}"
                decoded = patched_reader(entry)(url, entry.variable)
                if decoded is None:
                    self.skipTest(f"{url} holds no record of {entry.variable}")
                first = decoded.time[0]
                var = spz.get_data(f'cda/{dataset_id}/{entry.name}', first, first + np.timedelta64(1, 'h'),
                                   method='FILE')
                self.assertIsNotNone(var, msg)
                self.assertEqual(var.time.ndim, 1, msg)
                self.assertEqual(len(var.time), var.values.shape[0], msg)
                self.assertTrue(np.all(np.diff(var.time) > np.timedelta64(0, 'ns')), msg)


if __name__ == '__main__':
    unittest.main()
