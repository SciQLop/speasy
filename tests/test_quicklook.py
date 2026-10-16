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
from speasy.plotting.quicklook import figure, render, windows  # noqa: E402
from speasy.plotting.sciqlop_template import load_template  # noqa: E402
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis, VariableAxis  # noqa: E402

__HERE__ = os.path.dirname(os.path.abspath(__file__))
_CDF = f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf"


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _product(speasy_id, kind='sciqlop.speasy', graph_type='Line', y_axis='y', path='', knobs=None):
    return {'path': path, 'label': '', 'kind': kind, 'speasy_id': speasy_id, 'graph_type': graph_type,
            'knobs': knobs or {}, 'y_axis': y_axis}


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

    def test_not_a_template_says_so(self):
        with self.assertRaisesRegex(ValueError, r"t\.json is not a SciQLop panel template"):
            load_template(self.write({'hello': 1}))


class TestWindows(unittest.TestCase):

    def test_daily_windows_are_clipped_to_the_range(self):
        self.assertEqual(windows('2018-01-01T12', '2018-01-03T06', 'daily'),
                         [(_utc(2018, 1, 1, 12), _utc(2018, 1, 2)), (_utc(2018, 1, 2), _utc(2018, 1, 3)),
                          (_utc(2018, 1, 3), _utc(2018, 1, 3, 6))])

    def test_a_stop_on_a_boundary_adds_no_empty_window(self):
        self.assertEqual(windows('2018-01-01', '2018-01-03', 'daily'),
                         [(_utc(2018, 1, 1), _utc(2018, 1, 2)), (_utc(2018, 1, 2), _utc(2018, 1, 3))])

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


if __name__ == '__main__':
    unittest.main()
