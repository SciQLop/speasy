import unittest
from datetime import datetime, timezone

import numpy as np
import pycdfpp

import speasy as spz
from speasy.data_providers.cda import _archive_params_for
from speasy.data_providers.cda._virtual import with_virtuals

START, STOP = datetime(2000, 1, 1, 0, 20, tzinfo=timezone.utc), datetime(2000, 1, 1, 0, 50, tzinfo=timezone.utc)


def _arr_slice_master(arr_dim: int, arr_index: int) -> pycdfpp.CDF:
    master = pycdfpp.CDF()
    master.add_variable('grid', values=np.zeros((0, 3, 4), dtype=np.float32))
    master.add_variable('slice', values=np.zeros((0, 4 if arr_dim == 0 else 3), dtype=np.float32),
                        attributes={'VIRTUAL': 'true', 'FUNCT': 'arr_slice', 'COMPONENT_0': 'grid',
                                    'ARR_INDEX': [np.int32(arr_index)], 'ARR_DIM': [np.int32(arr_dim)]})
    return master


def _data_file(with_empty_slice: bool) -> pycdfpp.CDF:
    cdf = pycdfpp.CDF()
    cdf.add_variable('grid', values=np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4))
    if with_empty_slice:
        cdf.add_variable('slice', values=np.zeros((0, 4), dtype=np.float32))
    return cdf


class ArrSlice(unittest.TestCase):
    # ARR_DIM counts the dimensions of one record, see arr_slice in
    # https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/source/virtual_funcs.pro
    def test_arr_dim_0_slices_the_first_record_dimension(self):
        cdf = with_virtuals(_data_file(with_empty_slice=True), _arr_slice_master(arr_dim=0, arr_index=1))
        np.testing.assert_array_equal(cdf['slice'].values, cdf['grid'].values[:, 1, :])

    def test_arr_dim_1_slices_the_second_record_dimension(self):
        cdf = with_virtuals(_data_file(with_empty_slice=True), _arr_slice_master(arr_dim=1, arr_index=2))
        np.testing.assert_array_equal(cdf['slice'].values, cdf['grid'].values[:, :, 2])

    def test_files_without_the_virtual_variable_get_it_too(self):
        cdf = with_virtuals(_data_file(with_empty_slice=False), _arr_slice_master(arr_dim=0, arr_index=0))
        np.testing.assert_array_equal(cdf['slice'].values, cdf['grid'].values[:, 0, :])


def _archive_params(product: str):
    inventory = spz.inventories.flat_inventories.cda
    dataset, variable = product.split('/')
    return _archive_params_for(inventory.datasets[dataset], inventory.parameters[product], variable, START, STOP)


class FastFromFiles(unittest.TestCase):
    def test_arr_slice_virtual_is_served_from_files(self):
        self.assertIsNotNone(_archive_params('FA_ESA_L2_EES/energy_median'))

    def test_variable_with_arr_slice_axes_is_served_from_files(self):
        self.assertIsNotNone(_archive_params('FA_ESA_L2_EES/eflux'))

    def test_other_virtual_functions_still_go_to_the_web_service(self):
        self.assertIsNone(_archive_params('FA_ESA_L2_EES/eflux_movie'))   # alternate_view

    def test_files_and_web_service_agree(self):
        for product in ('FA_ESA_L2_EES/energy_median', 'FA_ESA_L2_EES/eflux'):
            with self.subTest(product=product):
                from_files = spz.get_data(f'cda/{product}', START, STOP, method='FILE', disable_cache=True)
                from_api = spz.get_data(f'cda/{product}', START, STOP, method='API', disable_cache=True,
                                        disable_proxy=True)
                np.testing.assert_array_equal(from_files.time, from_api.time)
                np.testing.assert_array_equal(from_files.values, from_api.values)
                self.assertListEqual([ax.values.shape for ax in from_files.axes],
                                     [ax.values.shape for ax in from_api.axes])


if __name__ == '__main__':
    unittest.main()
