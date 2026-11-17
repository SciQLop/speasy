import unittest
from datetime import datetime, timezone

import numpy as np
import pycdfpp

import speasy as spz
from speasy.data_providers.cda import _archive_params_for
from speasy.data_providers.cda._virtual import pruned, with_virtuals

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

    def test_arr_dim_follows_the_declared_dimensions_of_column_major_files(self):
        # IDL indexes ARR_DIM in the order the CDF declares its dimensions, whatever the majority
        grid = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
        column_major = pycdfpp.CDF()
        column_major.majority = pycdfpp.Majority.column
        column_major.add_variable('grid', values=grid)
        reloaded = pycdfpp.load(bytes(pycdfpp.save(column_major)))
        self.assertEqual(reloaded.majority, pycdfpp.Majority.column)
        cdf = with_virtuals(reloaded, _arr_slice_master(arr_dim=0, arr_index=1))
        np.testing.assert_array_equal(cdf['slice'].values, grid[:, 1, :])

    def test_a_non_record_varying_component_gives_a_non_record_varying_slice(self):
        # IDL reads such a component without any record axis, so the result has none either
        cdf = pycdfpp.CDF()
        cdf.add_variable('grid', values=np.arange(3 * 4, dtype=np.float32).reshape(1, 3, 4), is_nrv=True)
        cdf = with_virtuals(cdf, _arr_slice_master(arr_dim=1, arr_index=2))
        self.assertTrue(cdf['slice'].is_nrv)
        np.testing.assert_array_equal(cdf['slice'].values, cdf['grid'].values[:, :, 2])

    def test_size_1_dimensions_are_dropped_like_idl_reform_does(self):
        # REFORM drops every size-1 dimension, not only the sliced one; the record axis stays
        cdf = pycdfpp.CDF()
        cdf.add_variable('grid', values=np.arange(2 * 3 * 1, dtype=np.float32).reshape(2, 3, 1))
        cdf = with_virtuals(cdf, _arr_slice_master(arr_dim=0, arr_index=1))
        np.testing.assert_array_equal(cdf['slice'].values, cdf['grid'].values[:, 1, 0])

    def test_a_single_record_is_kept_as_a_record(self):
        cdf = pycdfpp.CDF()
        cdf.add_variable('grid', values=np.arange(3 * 4, dtype=np.float32).reshape(1, 3, 4))
        cdf = with_virtuals(cdf, _arr_slice_master(arr_dim=0, arr_index=1))
        self.assertEqual(cdf['slice'].values.shape, (1, 4))


def _sparse_file(sparse_records, n_records=5) -> pycdfpp.CDF:
    cdf = pycdfpp.CDF()
    cdf.add_variable('epoch', values=pycdfpp.to_tt2000(np.datetime64('2010-01-01', 'ns') +
                                                       np.arange(n_records) * np.timedelta64(1, 's')),
                     data_type=pycdfpp.DataType.CDF_TIME_TT2000)
    cdf.add_variable('grid', values=np.arange(1, 13, dtype=np.float32).reshape(1, 3, 4),
                     sparse_records=sparse_records, pad_value=np.float32(-1.))
    return cdf


def _sparse_master() -> pycdfpp.CDF:
    master = _arr_slice_master(arr_dim=0, arr_index=1)
    master['slice'].add_attribute('DEPEND_0', 'epoch')
    return master


class SparseRecords(unittest.TestCase):
    # a record-varying component may write fewer records than the epoch has, the CDF sparse records mode then
    # says what the others hold: WI_EPACT_STEP-* write energy_center once a file with prev_sparse_records
    def test_previous_sparse_records_repeat_the_last_record(self):
        cdf = with_virtuals(_sparse_file(pycdfpp.SparseRecords.prev_sparse_records), _sparse_master())
        np.testing.assert_array_equal(cdf['slice'].values, np.repeat([[5., 6., 7., 8.]], 5, axis=0))

    def test_pad_sparse_records_hold_the_pad_value(self):
        cdf = with_virtuals(_sparse_file(pycdfpp.SparseRecords.pad_sparse_records), _sparse_master())
        np.testing.assert_array_equal(cdf['slice'].values, [[5., 6., 7., 8.]] + [[-1.] * 4] * 4)

    def test_no_sparse_records_keeps_what_the_file_holds(self):
        cdf = with_virtuals(_sparse_file(pycdfpp.SparseRecords.no_sparse_records), _sparse_master())
        np.testing.assert_array_equal(cdf['slice'].values, [[5., 6., 7., 8.]])


def _copy_master(funct: str, component: str = 'grid') -> pycdfpp.CDF:
    master = pycdfpp.CDF()
    master.add_variable('view', values=np.zeros((0, 3, 4), dtype=np.float32),
                        attributes={'VIRTUAL': 'true', 'FUNCT': funct, 'COMPONENT_0': component})
    return master


class CopiedViews(unittest.TestCase):
    # alternate_view reuses the component's data handle as is (virtual_funcs.pro), clone reads the component's
    # data (read_myCDF.pro): both give the component's values
    def test_alternate_view_and_clone_copy_the_component(self):
        for funct in ('alternate_view', 'clone', 'ALTERNATE_VIEW'):
            with self.subTest(funct=funct):
                cdf = with_virtuals(_data_file(with_empty_slice=False), _copy_master(funct))
                np.testing.assert_array_equal(cdf['view'].values, cdf['grid'].values)

    def test_a_copy_of_a_non_record_varying_component_stays_non_record_varying(self):
        cdf = pycdfpp.CDF()
        cdf.add_variable('grid', values=np.arange(12, dtype=np.float32).reshape(1, 3, 4), is_nrv=True)
        cdf = with_virtuals(cdf, _copy_master('alternate_view'))
        self.assertTrue(cdf['view'].is_nrv)
        np.testing.assert_array_equal(cdf['view'].values, cdf['grid'].values)

    def test_a_record_varying_clone_of_a_non_record_varying_component_repeats_it_per_record(self):
        # read_myCDF.pro's MAKE_VARY, STA_L1_SEPT clones NRV spectra into record varying products
        cdf = _sparse_file(pycdfpp.SparseRecords.no_sparse_records)
        cdf._remove_variable('grid')
        cdf.add_variable('grid', values=np.arange(12, dtype=np.float32).reshape(1, 3, 4), is_nrv=True)
        master = _copy_master('clone')
        master['view'].add_attribute('DEPEND_0', 'epoch')
        cdf = with_virtuals(cdf, master)
        self.assertFalse(cdf['view'].is_nrv)
        np.testing.assert_array_equal(cdf['view'].values, np.repeat(cdf['grid'].values, 5, axis=0))

    def test_the_view_takes_the_numeric_type_the_master_declares(self):
        # CDAWeb writes a virtual variable with its master type: RBSPA_REL03_ECT-REPT-SCI-L2 B_Calc_TT is a CDF_REAL4
        # view of a B_Calc the files hold as doubles
        cdf = pycdfpp.CDF()
        cdf.add_variable('grid', values=np.linspace(0, 1, 24).reshape(2, 3, 4))
        cdf = with_virtuals(cdf, _copy_master('alternate_view'))
        self.assertEqual(cdf['view'].type, pycdfpp.DataType.CDF_FLOAT)
        np.testing.assert_array_equal(cdf['view'].values, cdf['grid'].values.astype(np.float32))

    def test_flip_vert_reverses_the_first_dimension_of_each_record(self):
        # IDL's reverse(img[*,*,j]) reverses the first dimension IDL indexes, the first declared one
        cdf = with_virtuals(_data_file(with_empty_slice=False), _copy_master('alternate_view_flip_vert'))
        np.testing.assert_array_equal(cdf['view'].values, cdf['grid'].values[:, ::-1, :])

    def test_a_virtual_component_is_computed_first_whatever_the_master_order(self):
        master = _copy_master('alternate_view', component='slice')
        master.add_variable('slice', values=np.zeros((0, 4), dtype=np.float32),
                            attributes={'VIRTUAL': 'true', 'FUNCT': 'arr_slice', 'COMPONENT_0': 'grid',
                                        'ARR_INDEX': [np.int32(1)], 'ARR_DIM': [np.int32(0)]})
        cdf = with_virtuals(_data_file(with_empty_slice=True), master)
        np.testing.assert_array_equal(cdf['view'].values, cdf['grid'].values[:, 1, :])


class Pruning(unittest.TestCase):
    # read_with_virtuals writes the patched file back before the ISTP loader reads it, and writing a whole MMS or
    # MAVEN file decompressed every variable: 3 GB for one product. Only what the product references is kept.
    def test_keeps_the_variable_and_everything_it_references_drops_the_rest(self):
        cdf = pycdfpp.CDF()
        for name in ('epoch', 'grid', 'labels', 'unrelated', 'axis'):
            cdf.add_variable(name, values=np.zeros((2, 3), dtype=np.float32))
        cdf['grid'].add_attribute('DEPEND_0', 'epoch')
        cdf['grid'].add_attribute('DEPEND_1', 'axis')
        master = _copy_master('alternate_view')
        master['view'].add_attribute('LABL_PTR_1', 'labels')
        master['view'].add_attribute('CATDESC', 'not a variable name')
        kept_cdf, kept_master = pruned('view', cdf, master)
        self.assertSetEqual(set(kept_cdf.keys()), {'epoch', 'grid', 'labels', 'axis'})
        self.assertSetEqual(set(kept_master.keys()), {'view'})


def _archive_params(product: str, start=START, stop=STOP):
    inventory = spz.inventories.flat_inventories.cda
    dataset, variable = product.split('/')
    return _archive_params_for(inventory.datasets[dataset], inventory.parameters[product], variable, start, stop)


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


class SparseComponentFromFiles(unittest.TestCase):
    def test_slice_of_a_previous_sparse_records_component_matches_the_web_service(self):
        # ENERGY_CENTER_T1, the energy axis of FLUX_T1, slices energy_center: written once per yearly file
        product = 'cda/WI_EPACT_STEP-DIRECTIONAL-DIFF-H-FLUX-10MIN/FLUX_T1'
        start, stop = '2010-01-01T00:06:06.997', '2010-01-01T03:47:42.008'
        self.assertIsNotNone(_archive_params(product[4:], datetime(2010, 1, 1, 0, 6, tzinfo=timezone.utc),
                                             datetime(2010, 1, 1, 3, 48, tzinfo=timezone.utc)))
        from_files = spz.get_data(product, start, stop, method='FILE', disable_cache=True)
        from_api = spz.get_data(product, start, stop, method='API', disable_cache=True, disable_proxy=True)
        np.testing.assert_array_equal(from_files.values, from_api.values)
        np.testing.assert_array_equal(from_files.axes[2].values, from_api.axes[2].values)


if __name__ == '__main__':
    unittest.main()
