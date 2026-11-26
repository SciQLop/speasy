import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import matplotlib
import numpy as np

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

from speasy.cli import main  # noqa: E402
from speasy.core.codecs import get_codec  # noqa: E402
from speasy.plotting.quicklook import fetch_window, figure, render, windows  # noqa: E402
from speasy.plotting.sciqlop_template import apply_operations, checked_operations, load_template  # noqa: E402
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis, VariableAxis  # noqa: E402
from speasy.signal.reduction import integrate, sel  # noqa: E402

__HERE__ = os.path.dirname(os.path.abspath(__file__))
_CDF = f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf"


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _product(speasy_id, kind='sciqlop.speasy', graph_type='Line', y_axis='y', path='', knobs=None, **extra):
    return {'path': path, 'label': '', 'kind': kind, 'speasy_id': speasy_id, 'graph_type': graph_type,
            'knobs': knobs or {}, 'y_axis': y_axis, **extra}


def _plot(*products, y_log=False, y2_log=False, z_log=False):
    return {'products': list(products), 'y_axis': {'log': y_log, 'range': [1.0, 10.0]},
            'y2_axis': {'log': y2_log, 'range': None}, 'z_axis': {'log': z_log, 'range': None}}


def _v3(*plot_nodes, time_range=None, panel_kind='sciqlop.time_panel'):
    return {'version': 3, 'name': 'tree', 'description': '', 'max_zoom_seconds': None, 'intervals': [],
            'panel': {'kind': panel_kind, 'id': '', 'config': {'time_range': time_range},
                      'slots': {'plots': list(plot_nodes)}}}


def _timeseries(plot):
    return {'kind': 'sciqlop.timeseries', 'id': '', 'config': plot, 'slots': {}}


_V2 = {"name": "mms_overview", "description": "", "version": 2,
       "time_range": {"start": "2015-11-18T02:14:30+00:00", "stop": "2015-11-18T03:34:00+00:00"},
       "plots": [{"products": [{"path": "speasy//cda//MMS//MMS1//FGM//MMS1_FGM_SRVY_L2//mms1_fgm_b_gse_srvy_l2",
                                "label": "mms1_fgm_b_gse_srvy_l2", "kind": "speasy",
                                "speasy_id": "cda/MMS1_FGM_SRVY_L2/mms1_fgm_b_gse_srvy_l2",
                                "graph_type": "SciQLopLineGraphFunction", "knobs": {}, "y_axis": "y"}],
                  "y_axis": {"log": False, "range": [-62.3, 65.3]},
                  "y2_axis": None, "z_axis": {"log": False, "range": [0.0, 6.0]}}],
       "intervals": [], "max_zoom_seconds": 86400.0}


class _TempDir(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, doc, name='t.json'):
        path = os.path.join(self.dir, name)
        with open(path, 'w') as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return path


class TestLoadTemplate(_TempDir):

    def test_reads_a_v2_template(self):
        t = load_template(self.write(_V2))
        self.assertEqual(t.name, 'mms_overview')
        self.assertEqual(t.time_range, ('2015-11-18T02:14:30+00:00', '2015-11-18T03:34:00+00:00'))
        self.assertEqual([p.speasy_id for p in t.plots[0].products], ['cda/MMS1_FGM_SRVY_L2/mms1_fgm_b_gse_srvy_l2'])
        self.assertFalse(t.plots[0].y_log)
        self.assertEqual(t.skipped, ())

    def test_reads_a_v3_template(self):
        doc = _v3(_timeseries(_plot(_product('amda/imf'), y_log=True)),
                  time_range={'start': '2020-01-01T00:00:00+00:00', 'stop': '2020-01-02T00:00:00+00:00'})
        t = load_template(self.write(doc))
        self.assertEqual(t.plots[0].products[0].speasy_id, 'amda/imf')
        self.assertTrue(t.plots[0].y_log)
        self.assertEqual(t.time_range, ('2020-01-01T00:00:00+00:00', '2020-01-02T00:00:00+00:00'))

    def test_reads_yaml_with_legacy_tuples(self):
        yaml_doc = ("name: y\nversion: 2\ntime_range: null\nplots:\n- products:\n  - path: ''\n    label: ''\n"
                    "    kind: speasy\n    speasy_id: amda/imf\n    graph_type: Line\n    knobs: {}\n    y_axis: y\n"
                    "  y_axis: {log: false, range: !!python/tuple [1.0, 2.0]}\n  y2_axis: null\n"
                    "  z_axis: {log: false, range: null}\nintervals: []\n")
        t = load_template(self.write(yaml_doc, name='t.yaml'))
        self.assertEqual(t.plots[0].products[0].speasy_id, 'amda/imf')

    def test_path_is_resolved_when_speasy_id_is_missing(self):
        doc = _v3(_timeseries(_plot(_product(None, path='speasy//amda//imf'))))
        t = load_template(self.write(doc), resolve_path=lambda segments: '/'.join(segments))
        self.assertEqual(t.plots[0].products[0].speasy_id, 'amda/imf')

    def test_unresolvable_path_is_skipped_with_a_hint(self):
        doc = _v3(_timeseries(_plot(_product(None, path='speasy//amda//gone'), _product('amda/imf'))))
        t = load_template(self.write(doc), resolve_path=lambda segments: None)
        self.assertEqual([p.speasy_id for p in t.plots[0].products], ['amda/imf'])
        self.assertRegex(t.skipped[0], r"speasy//amda//gone.*not found")

    def test_non_speasy_products_are_skipped_by_name(self):
        doc = _v3(_timeseries(_plot(_product(None, kind='sciqlop.vp', path='vp//my_product'),
                                    _product('amda/imf'))))
        t = load_template(self.write(doc))
        self.assertEqual([p.speasy_id for p in t.plots[0].products], ['amda/imf'])
        self.assertRegex(t.skipped[0], r"vp//my_product.*sciqlop\.vp")

    def test_plugin_plot_kinds_are_skipped_by_name(self):
        doc = _v3(_timeseries(_plot(_product('amda/imf'))),
                  {'kind': 'pt_demo.slice_plot', 'id': '', 'config': {'plane': 'XY'}, 'slots': {}})
        t = load_template(self.write(doc))
        self.assertEqual(len(t.plots), 1)
        self.assertIn("pt_demo.slice_plot", t.skipped[0])

    def test_plot_left_empty_is_dropped(self):
        doc = _v3(_timeseries(_plot(_product(None, kind='sciqlop.function'))), _timeseries(_plot(_product('amda/imf'))))
        t = load_template(self.write(doc))
        self.assertEqual(len(t.plots), 1)

    def test_non_time_panel_is_reported(self):
        t = load_template(self.write(_v3(panel_kind='my_plugin.panel')))
        self.assertEqual(t.plots, ())
        self.assertIn("my_plugin.panel", t.skipped[0])

    def test_knobs_become_get_data_kwargs(self):
        doc = _v3(_timeseries(_plot(_product('ssc/wind', knobs={'ssc': 'gse'}),
                                    _product('cdpp3dview/x', knobs={'cdpp3dview': 'J2000'}),
                                    _product('amda/tpl', knobs={'sampling': '60'}))))
        products = load_template(self.write(doc)).plots[0].products
        self.assertEqual([p.kwargs for p in products],
                         [{'coordinate_system': 'gse'}, {'coordinate_frame': 'J2000'},
                          {'product_inputs': {'sampling': '60'}}])

    def test_colormap_and_right_axis_are_kept(self):
        doc = _v3(_timeseries(_plot(_product('a/spec', graph_type='SciQLopColorMap'),
                                    _product('a/line', y_axis='y2'))))
        spec, line = load_template(self.write(doc)).plots[0].products
        self.assertTrue(spec.colormap)
        self.assertFalse(spec.right_axis)
        self.assertTrue(line.right_axis)

    def test_reduce_is_read_with_the_product_in_v2_and_v3(self):
        ops = [{'op': 'mean', 'axis': 'phi'}, {'op': 'mean', 'axis': 'theta', 'weights': [1.0, 2.0]}]
        v2 = {**_V2, 'plots': [{**_V2['plots'][0], 'products': [{**_V2['plots'][0]['products'][0], 'reduce': ops}]}]}
        v3 = _v3(_timeseries(_plot(_product('a/dist', reduce=ops), _product('a/line'))))
        for doc in (v2, v3):
            with self.subTest(version=doc['version']):
                products = load_template(self.write(doc)).plots[0].products
                self.assertEqual(products[0].reduce, tuple(ops))
        self.assertEqual(load_template(self.write(v3)).plots[0].products[1].reduce, ())

    def test_reduce_is_read_from_yaml(self):
        yaml_doc = ("name: y\nversion: 2\ntime_range: null\nplots:\n- products:\n  - kind: speasy\n"
                    "    speasy_id: a/dist\n    graph_type: SciQLopColorMap\n    reduce:\n"
                    "    - {op: mean, axis: phi}\n    - {op: sel, axis: energy, value: [10, 1000]}\n")
        product = load_template(self.write(yaml_doc, name='t.yaml')).plots[0].products[0]
        self.assertEqual(product.reduce, ({'op': 'mean', 'axis': 'phi'},
                                          {'op': 'sel', 'axis': 'energy', 'value': [10, 1000]}))

    def test_a_bad_reduce_is_refused_at_load_naming_the_product(self):
        for reduce, message in (([{'op': 'average', 'axis': 'phi'}], r"'op' must be one of isel, sel, sum, mean"),
                                ([{'op': 'mean'}], r"mean takes 'axis' and optionally 'weights', got"),
                                ('mean phi', r"a list of operations"),
                                (['mean phi'], r"each operation is a dict")):
            path = self.write(_v3(_timeseries(_plot(_product('a/dist', path='speasy//a//dist', reduce=reduce)))))
            with self.subTest(reduce=reduce), self.assertRaisesRegex(ValueError, r"product speasy//a//dist: .*" + message):
                load_template(path)

    def test_not_a_template_says_so(self):
        path = self.write({'hello': 1})
        with self.assertRaisesRegex(ValueError, r"t\.json is not a SciQLop panel template"):
            load_template(path)


class TestWindows(unittest.TestCase):

    def test_daily_windows_are_clipped_to_the_range(self):
        self.assertEqual(windows('2018-01-01T12', '2018-01-03T06', 'daily'),
                         [(_utc(2018, 1, 1, 12), _utc(2018, 1, 2)), (_utc(2018, 1, 2), _utc(2018, 1, 3)),
                          (_utc(2018, 1, 3), _utc(2018, 1, 3, 6))])

    def test_a_stop_on_a_boundary_adds_no_empty_window(self):
        self.assertEqual(windows('2018-01-01', '2018-01-03', 'daily'),
                         [(_utc(2018, 1, 1), _utc(2018, 1, 2)), (_utc(2018, 1, 2), _utc(2018, 1, 3))])

    def test_an_unknown_split_lists_the_valid_ones(self):
        with self.assertRaisesRegex(ValueError, r"Unknown split 'weekly': use daily, monthly, yearly or none"):
            windows('2018-01-01', '2018-03-01', 'weekly')

    def test_none_is_a_single_window(self):
        self.assertEqual(windows('2018-01-01', '2018-03-01', 'none'), [(_utc(2018, 1, 1), _utc(2018, 3, 1))])


def _line_var():
    return get_codec('cdf').load_variable(file=_CDF, variable='BGSEc')


def _spectro_var():
    time = np.arange('2022-01-01T00', '2022-01-01T02', dtype='datetime64[m]').astype('datetime64[ns]')
    return SpeasyVariable(axes=[VariableTimeAxis(values=time),
                                VariableAxis(values=np.logspace(1, 4, 16), name='energy')],
                          values=DataContainer(values=np.random.rand(len(time), 16), name='flux',
                                               meta={'DISPLAY_TYPE': 'spectrogram'}),
                          columns=[f"c{i}" for i in range(16)])


class TestRender(_TempDir):

    def test_renders_lines_colormaps_and_right_axes_without_pyplot_figures(self):
        doc = _v3(_timeseries(_plot(_product('a/line'))),
                  _timeseries(_plot(_product('a/spec', graph_type='SciQLopColorMap'), z_log=True)),
                  _timeseries(_plot(_product('a/left'), _product('a/right', y_axis='y2'))))
        template = load_template(self.write(doc))
        data = [[_line_var()], [_spectro_var()], [_line_var(), None]]
        target = os.path.join(self.dir, 'out.png')
        render(template, data, _utc(2022, 1, 1), _utc(2022, 1, 2), target)
        self.assertGreater(os.path.getsize(target), 0)
        self.assertEqual(plt.get_fignums(), [])


def _distribution_var(values=None, fill=None):
    """(time, phi, theta, energy), like a 3D particle distribution."""
    time = np.arange('2022-01-01T00', '2022-01-01T02', dtype='datetime64[m]').astype('datetime64[ns]')
    shape = (len(time), 8, 4, 16)
    values = np.random.rand(*shape) + 1. if values is None else values
    return SpeasyVariable(axes=[VariableTimeAxis(values=time),
                                VariableAxis(values=np.linspace(0, 337.5, 8), name='dist_phi'),
                                VariableAxis(values=np.linspace(22.5, 157.5, 4), name='dist_theta'),
                                VariableAxis(values=np.logspace(1, 4, 16), name='dist_energy')],
                          values=DataContainer(values=values, name='dist', meta={} if fill is None else {'FILLVAL': fill}))


class TestOperations(unittest.TestCase):
    OPS = [{'op': 'sel', 'axis': 'energy', 'value': [10., 1000.]},
           {'op': 'mean', 'axis': 'theta', 'weights': [1., 2., 3., 4.]},
           {'op': 'integrate', 'axis': 1}]

    def setUp(self):
        self.dist = _distribution_var()

    def test_operations_are_applied_in_order(self):
        selected = sel(self.dist, 'energy', slice(10., 1000.))
        expected = integrate(np.average(selected, axis=2, weights=[1., 2., 3., 4.]), 1)
        np.testing.assert_allclose(apply_operations(self.dist, self.OPS).values, expected.values)

    def test_each_op_and_what_it_does(self):
        v = self.dist
        for op, expected in (({'op': 'isel', 'axis': 'theta', 'index': 1}, v[:, :, 1]),
                             ({'op': 'isel', 'axis': 'theta', 'index': [0, 2]}, v[:, :, 0:2]),
                             ({'op': 'sel', 'axis': 'energy', 'value': 100., 'method': 'nearest'},
                              sel(v, 'energy', 100., method='nearest')),
                             ({'op': 'sum', 'axis': 'phi'}, np.sum(v, axis=1)),
                             ({'op': 'mean', 'axis': 'phi'}, np.mean(v, axis=1)),
                             ({'op': 'mean', 'axis': 'theta', 'weights': [1., 0., 0., 3.]},
                              np.average(v, axis=2, weights=[1., 0., 0., 3.])),
                             ({'op': 'integrate', 'axis': 'phi', 'edges': list(range(9))}, np.sum(v, axis=1))):
            with self.subTest(op=op):
                result = apply_operations(v, [op])
                np.testing.assert_allclose(result.values, expected.values)
                self.assertEqual(result.axes_labels, expected.axes_labels)

    def test_sum_and_mean_skip_fill_and_nan_and_give_nan_where_all_are_missing(self):
        values = np.array(self.dist.values)
        values[0, :, 0, 0] = -1e31
        values[1, 2, 1, 3] = np.nan
        v = _distribution_var(values=values, fill=-1e31)
        for op, function in (('sum', np.nansum), ('mean', np.nanmean)):
            with self.subTest(op=op):
                result = apply_operations(v, [{'op': op, 'axis': 'phi'}]).values
                self.assertTrue(np.isnan(result[0, 0, 0]))
                np.testing.assert_allclose(result[1, 1, 3], function(np.delete(values[1, :, 1, 3], 2)))
                np.testing.assert_allclose(result[2], function(values[2], axis=0))

    def test_a_weighted_mean_drops_missing_values_from_the_weights(self):
        values = np.ones(self.dist.values.shape)
        values[:, :, 3, :] = np.nan
        v = _distribution_var(values=values)
        result = apply_operations(v, [{'op': 'mean', 'axis': 'theta', 'weights': [1., 2., 3., 100.]}])
        np.testing.assert_allclose(result.values, 1.)

    def test_weights_need_the_shape_of_the_axis(self):
        v = self.dist
        with self.assertRaisesRegex(ValueError, r"weights for 'dist_theta' must have shape \(4,\).*got \(2,\)"):
            apply_operations(v, [{'op': 'mean', 'axis': 'theta', 'weights': [1., 2.]}])

    def test_malformed_operations_say_what_is_allowed(self):
        for op, message in (({'op': 'average', 'axis': 'x'}, r"'op' must be one of isel, sel, sum, mean, integrate"),
                            ({'mean': 'x'}, r"'op' must be one of"),
                            ({'op': 'sum'}, r"sum takes 'axis', got"),
                            ({'op': 'isel', 'axis': 'x'}, r"isel takes 'axis', 'index', got"),
                            ({'op': 'sum', 'axis': 'x', 'weights': [1]}, r"sum takes 'axis', got .*weights"),
                            ({'op': 'mean', 'axis': 'x', 'unit': 'eV'}, r"mean takes 'axis' and optionally 'weights'")):
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, message):
                checked_operations([op])

    def test_an_isel_index_is_a_position_or_a_start_stop_pair(self):
        for index in ([1], [1, 3, 2], [], 'a', 1.5, True, [0, 'x']):
            with self.subTest(index=index), self.assertRaisesRegex(
                    ValueError, r"isel's 'index' is a position like 3 or a \[start, stop\] pair like \[1, 3\], got"):
                checked_operations([{'op': 'isel', 'axis': 'x', 'index': index}])
        for index in (2, -1, [1, 3], (0, 2), [-3, -1]):
            with self.subTest(index=index):
                checked_operations([{'op': 'isel', 'axis': 'x', 'index': index}])

    def test_the_list_and_its_items_are_checked(self):
        self.assertEqual(checked_operations(self.OPS), tuple(self.OPS))
        for operations, message in (('mean phi', r"a list of operations like \[\{'op': 'mean', 'axis': 'phi'\}\]"),
                                    ({'op': 'sum', 'axis': 'x'}, r"a list of operations"),
                                    (['mean phi'], r"each operation is a dict like \{'op': 'mean', 'axis': 'phi'\}"),
                                    ([{'op': 'sum', 'axis': 'x'}, {'op': 'sum'}], r"sum takes 'axis', got")):
            with self.subTest(operations=operations), self.assertRaisesRegex(ValueError, message):
                checked_operations(operations)

    def test_nothing_runs_when_a_later_operation_is_malformed(self):
        operations = [{'op': 'sum', 'axis': 'nope'}, {'op': 'average', 'axis': 'phi'}]
        with self.assertRaisesRegex(ValueError, r"'op' must be one of"):
            apply_operations(self.dist, operations)


class TestPublicTemplateApi(unittest.TestCase):
    """SciQLop applies a template's 'reduce' list with these names; renaming them breaks SciQLop, so this fails."""

    def test_the_names_other_tools_use(self):
        import speasy.plotting.sciqlop_template as template
        from speasy.plotting.sciqlop_template import OPERATIONS, apply_operations
        from speasy.signal.reduction import dimension
        self.assertEqual(set(template.__all__), {'OPERATIONS', 'apply_operations'})
        self.assertEqual(set(OPERATIONS), {'isel', 'sel', 'sum', 'mean', 'integrate'})
        dist = _distribution_var()
        reduced = apply_operations(dist, [{'op': 'mean', 'axis': 'phi'}])
        np.testing.assert_allclose(reduced.values, np.nanmean(dist, axis=dimension(dist, 'phi')).values)


class TestReducedRender(_TempDir):

    def setUp(self):
        super().setUp()
        self.dist = _distribution_var()
        p = mock.patch('speasy.get_data', return_value=self.dist)
        p.start()
        self.addCleanup(p.stop)
        doc = _v3(_timeseries(_plot(_product('a/dist', graph_type='SciQLopColorMap',
                                             reduce=[{'op': 'mean', 'axis': 'phi'},
                                                     {'op': 'mean', 'axis': 'theta'}]), z_log=True)))
        self.template = load_template(self.write(doc))

    def test_a_3d_distribution_reduced_by_the_template_plots_as_a_spectrogram(self):
        data, failures = fetch_window(self.template, _utc(2022, 1, 1), _utc(2022, 1, 1, 2))
        self.assertEqual(failures, [])
        spectrum = data[0][0]
        self.assertEqual(spectrum.values.shape, (120, 16))
        self.assertEqual(spectrum.axes[1].name, 'dist_energy')
        np.testing.assert_allclose(spectrum.values, np.mean(self.dist.values, axis=(1, 2)))
        fig = figure(self.template, data, _utc(2022, 1, 1), _utc(2022, 1, 1, 2))
        self.assertEqual(len(fig.axes[0].collections), 1)  # one colormap mesh
        fig.savefig(os.path.join(self.dir, 'out.png'))
        self.assertEqual(plt.get_fignums(), [])

    def test_a_reduction_that_fails_on_the_data_is_a_product_failure(self):
        doc = _v3(_timeseries(_plot(_product('a/dist', reduce=[{'op': 'sum', 'axis': 'psi'}]))))
        data, failures = fetch_window(load_template(self.write(doc)), _utc(2022, 1, 1), _utc(2022, 1, 1, 2))
        self.assertEqual(data, [[None]])
        self.assertRegex(failures[0], r"a/dist: ValueError: No axis 'psi'")

    def test_a_window_without_data_is_not_reduced(self):
        with mock.patch('speasy.get_data', return_value=None):
            data, failures = fetch_window(self.template, _utc(2022, 1, 1), _utc(2022, 1, 1, 2))
        self.assertEqual((data, failures), ([[None]], []))


class TestTwinAxes(_TempDir):

    def test_right_axis_lines_get_their_own_colour_and_share_one_legend(self):
        doc = _v3(_timeseries(_plot(_product('a/left'), _product('a/right', y_axis='y2'), y2_log=True)))
        fig = figure(load_template(self.write(doc)), [[_line_var(), _line_var()]], _utc(2022, 1, 1), _utc(2022, 1, 2))
        ax, twin = fig.axes
        left_colors = {line.get_color() for line in ax.get_lines()}
        self.assertFalse(left_colors & {line.get_color() for line in twin.get_lines()})
        self.assertEqual(twin.get_yscale(), 'log')
        self.assertIsNone(twin.get_legend())
        self.assertEqual(len(ax.get_legend().get_texts()), len(ax.get_lines()) + len(twin.get_lines()))


class TestColorbarWithoutPyplot(unittest.TestCase):

    def test_colormap_on_a_given_axes_creates_no_pyplot_figure(self):
        from matplotlib.figure import Figure
        plt.close('all')
        _spectro_var().plot(ax=Figure().subplots())
        self.assertEqual(plt.get_fignums(), [])


class TestQuicklookCli(_TempDir):

    def setUp(self):
        super().setUp()
        p = mock.patch('speasy.get_data', return_value=_line_var())
        self.get_data = p.start()
        self.addCleanup(p.stop)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(list(argv))
        return code, out.getvalue()

    def template(self, time_range=None):
        doc = _v3(_timeseries(_plot(_product('amda/imf'), _product('ssc/wind', knobs={'ssc': 'gse'}))),
                  time_range=time_range)
        return self.write(doc, name='overview.json')

    def test_one_image_per_window(self):
        code, out = self.run_cli('quicklook', self.template(), '--start', '2022-01-01', '--stop', '2022-01-03',
                                 '--output-dir', self.dir, '--workers', '2')
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(f for f in os.listdir(self.dir) if f.endswith('.png')),
                         ['tree_20220101T000000.png', 'tree_20220102T000000.png'])
        self.assertIn(mock.call('ssc/wind', mock.ANY, mock.ANY, coordinate_system='gse'),
                      self.get_data.call_args_list)

    def test_time_range_defaults_to_the_template_one(self):
        code, _ = self.run_cli('quicklook', self.template({'start': '2022-01-01T00:00:00+00:00',
                                                           'stop': '2022-01-01T06:00:00+00:00'}),
                               '--output-dir', self.dir)
        self.assertEqual(code, 0)
        self.assertIn('tree_20220101T000000.png', os.listdir(self.dir))

    def test_needs_a_time_range(self):
        code, out = self.run_cli('quicklook', self.template(), '--output-dir', self.dir)
        self.assertEqual(code, 1)
        self.assertIn('--start', out)

    def test_a_failed_product_still_renders_the_others_and_exits_one(self):
        self.get_data.side_effect = lambda product, *a, **k: (_ for _ in ()).throw(RuntimeError('down')) \
            if product == 'ssc/wind' else _line_var()
        code, out = self.run_cli('quicklook', self.template(), '--start', '2022-01-01', '--stop', '2022-01-02',
                                 '--output-dir', self.dir)
        self.assertEqual(code, 1)
        self.assertIn('ssc/wind', out)
        self.assertIn('down', out)
        self.assertIn('tree_20220101T000000.png', os.listdir(self.dir))

    def test_skipped_parts_are_reported(self):
        doc = _v3(_timeseries(_plot(_product('amda/imf'), _product(None, kind='sciqlop.vp', path='vp//x'))))
        _, out = self.run_cli('quicklook', self.write(doc), '--start', '2022-01-01', '--stop', '2022-01-02',
                              '--output-dir', self.dir)
        self.assertIn('vp//x', out)

    def test_a_bad_reduce_is_a_clean_error(self):
        doc = _v3(_timeseries(_plot(_product('amda/imf', reduce=[{'op': 'average', 'axis': 'x'}]))))
        code, out = self.run_cli('quicklook', self.write(doc), '--start', '2022-01-01', '--stop', '2022-01-02')
        self.assertEqual(code, 1)
        self.assertRegex(out, r"Error: product .*amda/imf.*'op' must be one of")

    def test_missing_template_is_a_clean_error(self):
        code, out = self.run_cli('quicklook', 'nonexistent.json', '--start', '2022-01-01', '--stop', '2022-01-02')
        self.assertEqual(code, 1)
        self.assertRegex(out, r"Error: no such file: nonexistent\.json")

    def test_unparsable_start_is_named(self):
        code, out = self.run_cli('quicklook', self.template(), '--start', 'notadate', '--stop', '2022-01-02')
        self.assertEqual(code, 1)
        self.assertRegex(out, r"--start 'notadate' is not a date")


if __name__ == '__main__':
    unittest.main()
