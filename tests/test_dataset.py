import unittest

import numpy as np

from speasy.core.datetime_range import DateTimeRange
from speasy.core import epoch_to_datetime64
from speasy.products.dataset import Dataset
from speasy.products.variable import (DataContainer, SpeasyVariable,
                                      VariableTimeAxis)


def make_simple_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1.):
    time = np.arange(start, stop, step)
    values = time * coef
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(time))],
                          values=DataContainer(values=values, meta=None),
                          columns=["Values"])


def make_simple_dataset(name="test"):
    return Dataset(name=name, variables={'v1': make_simple_var(), 'v2': make_simple_var(), 'v3': make_simple_var()},
                   meta={})


class SpeasyDataset(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_accepts_a_dict_of_variables(self):
        ds = Dataset(name="test", variables={"v": make_simple_var()}, meta={})
        self.assertEqual(len(ds), 1)
        self.assertEqual("test", ds.name)

    def test_raises_if_given_variables_is_not_a_dict_of_variables(self):
        with self.assertRaises(TypeError):
            ds = Dataset(name='Should raise', variables={'this is not a var': 10.}, meta={})

    def test_can_be_indexed_by_variable_name(self):
        ds = Dataset(name="test", variables={"v": make_simple_var()}, meta={})
        self.assertIs(type(ds['v']), SpeasyVariable)

    def test_len_gives_variable_count(self):
        ds = Dataset(name="test", variables={}, meta={})
        self.assertEqual(len(ds), 0)
        ds = make_simple_dataset()
        self.assertEqual(len(ds), 3)

    def test_has_str_repr(self):
        ds = make_simple_dataset()
        repr = str(ds)
        self.assertIn('v1', repr)
        self.assertIn('v2', repr)

    def test_can_iterate_variables(self):
        ds = make_simple_dataset()
        var_list = [v for v in ds]
        self.assertListEqual(['v1', 'v2', 'v3'], var_list)

    def test_returns_true_if_variable_name_is_in_dataset(self):
        ds = make_simple_dataset()
        for v in ds:
            self.assertIn(v, ds)

    def test_returns_false_if_variable_name_is_not_in_dataset(self):
        ds = make_simple_dataset()
        self.assertNotIn('Not in', ds)

    def test_has_no_time_range_when_empty_or_has_empty_vars(self):
        ds = Dataset(name="test", variables={}, meta={})
        self.assertIsNone(ds.time_range())
        ds = make_simple_dataset()
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


if __name__ == '__main__':
    unittest.main()
