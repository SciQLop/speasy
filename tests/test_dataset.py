import unittest

from speasy.common.dataset import Dataset
from speasy.common.variable import SpeasyVariable
from speasy.common.datetime_range import DateTimeRange
import numpy as np


def make_simple_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1.):
    time = np.arange(start, stop, step)
    values = time * coef
    return SpeasyVariable(time=time, data=values, meta=None, columns=["Values"], y=None)


class SpeasyDataset(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_accepts_a_dict_of_variables(self):
        ds = Dataset(name="test", variables={"v": SpeasyVariable()}, meta={})
        self.assertEqual(len(ds), 1)
        self.assertEqual("test", ds.name)

    def test_raises_if_given_variables_is_not_a_dict_of_variables(self):
        with self.assertRaises(TypeError):
            ds = Dataset(name='Should raise', variables={'this is not a var': 10.}, meta={})

    def test_can_be_indexed_by_variable_name(self):
        ds = Dataset(name="test", variables={"v": SpeasyVariable()}, meta={})
        self.assertIs(type(ds['v']), SpeasyVariable)

    def test_len_gives_variable_count(self):
        ds = Dataset(name="test", variables={}, meta={})
        self.assertEqual(len(ds), 0)
        ds = Dataset(name="test", variables={'v1': SpeasyVariable(), 'v2': SpeasyVariable(), 'v3': SpeasyVariable()},
                     meta={})
        self.assertEqual(len(ds), 3)

    def test_has_str_repr(self):
        ds = Dataset(name="test", variables={'v1': SpeasyVariable(), 'v2': SpeasyVariable(), 'v3': SpeasyVariable()},
                     meta={})
        repr = str(ds)
        self.assertIn('v1', repr)
        self.assertIn('v2', repr)

    def test_can_iterate_variables(self):
        ds = Dataset(name="test", variables={'v1': SpeasyVariable(), 'v2': SpeasyVariable(), 'v3': SpeasyVariable()},
                     meta={})
        var_list = [v for v in ds]
        self.assertListEqual(['v1', 'v2', 'v3'], var_list)

    def test_returns_true_if_variable_name_is_in_dataset(self):
        ds = Dataset(name="test", variables={'v1': SpeasyVariable(), 'v2': SpeasyVariable(), 'v3': SpeasyVariable()},
                     meta={})
        for v in ds:
            self.assertIn(v, ds)

    def test_returns_false_if_variable_name_is_not_in_dataset(self):
        ds = Dataset(name="test", variables={'v1': SpeasyVariable(), 'v2': SpeasyVariable(), 'v3': SpeasyVariable()},
                     meta={})
        self.assertNotIn('Not in', ds)

    def test_has_no_time_range_when_empty_or_has_empty_vars(self):
        ds = Dataset(name="test", variables={}, meta={})
        self.assertIsNone(ds.time_range())
        ds = Dataset(name="test", variables={'v1': SpeasyVariable(), 'v2': SpeasyVariable(), 'v3': SpeasyVariable()},
                     meta={})
        self.assertIsNone(ds.time_range())

    def test_has_a_time_range_encompassing_all_variables(self):
        ds = Dataset(name="test", variables={'v1': make_simple_var(10., 100.), 'v2': make_simple_var(30., 40.),
                                             'v3': make_simple_var(60., 500.)},
                     meta={})
        self.assertEqual(DateTimeRange(10., 499.), ds.time_range())

    def test_is_plotable(self):
        try:
            import matplotlib.pyplot as plt
            ds = Dataset(name="test", variables={'v1': make_simple_var(10., 100.), 'v2': make_simple_var(30., 40.),
                                                 'v3': make_simple_var(60., 500.)},
                         meta={})
            ax = ds.plot()
            self.assertIsNotNone(ax)
        except ImportError:
            self.skipTest("Can't import matplotlib")
