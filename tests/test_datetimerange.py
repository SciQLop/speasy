import unittest
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.common.datetime_range import DateTimeRange
from spwc.common import span_utils
from spwc.cache import _round_for_cache
import operator


@ddt
class SpanTransComparaisons(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        ([1., 1.], [1., 1.], True),
        ([1., 10.], [0., 10.], False),
        ([1., 10.], [5., 15.], False),
        ([-1., 1.], [-.5, .5], True),
        ([-2., 2.], [-10., 10.], False)
    )
    @unpack
    def test_contains(self, span, other, expected_result):
        self.assertEqual(span_utils.contains(span, other), expected_result)

    @data(
        ([1., 1.], [1., 1.], True),
        ([1., 10.], [0., 10.], False),
        ([1., 10.], [1., 15.], False),
        (DateTimeRange(datetime(2001, 1, 8, 1, 0, 0), datetime(2001, 1, 8, 2, 0, 0)),
         [datetime(2001, 1, 8, 1, 0, 0), datetime(2001, 1, 8, 2, 0, 0)], True),
        ([datetime(2001, 1, 8, 1, 0, 0), datetime(2001, 1, 8, 2, 0, 0)],
         DateTimeRange(datetime(2001, 1, 8, 1, 0, 0), datetime(2001, 1, 8, 3, 0, 0)), False),
    )
    @unpack
    def test_equal(self, span, other, expected_result):
        self.assertEqual(span_utils.equals(span, other), expected_result)

    @data(
        ([1., 1.], [1., 1.], True),
        ([1., 10.], [0., 10.], True),
        ([1., 10.], [20., 25.], False),
        ([20., 25.], [1., 10.], False)
    )
    @unpack
    def test_intersects(self, span, other, expected_result):
        self.assertEqual(span_utils.intersects(span, other), expected_result)


@ddt
class SpanTransformations(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        ([1., 1.], 10., [1., 1.]),
        ([1., 10.], 1., [1., 10.]),
        ([-1., 1.], 2, [-2., 2.]),
        ([-2., 2.], .5, [-1., 1.]),
        ([datetime(2020, 1, 1), datetime(2020, 1, 2)], 1., [datetime(2020, 1, 1), datetime(2020, 1, 2)]),
        ([datetime(2020, 1, 2), datetime(2020, 1, 3)], 2., [datetime(2020, 1, 1, 12), datetime(2020, 1, 3, 12)]),
        ([datetime(2020, 1, 1), datetime(2020, 1, 5)], .5, [datetime(2020, 1, 2), datetime(2020, 1, 4)])
    )
    @unpack
    def test_zoom(self, span, factor, expected_result):
        self.assertEqual(span_utils.zoom(span, factor), expected_result)

    @data(
        ([1., 1.], 10., [11., 11.]),
        ([1., 10.], 1., [2., 11.]),
        ([-1., 1.], -2., [-3., -1.]),
        ([datetime(2020, 1, 1), datetime(2020, 1, 2)], timedelta(days=1), [datetime(2020, 1, 2), datetime(2020, 1, 3)]),
        ([datetime(2020, 1, 2), datetime(2020, 1, 2)], -timedelta(days=1), [datetime(2020, 1, 1), datetime(2020, 1, 1)])
    )
    @unpack
    def test_shift(self, span, distance, expected_result):
        self.assertEqual(span_utils.shift(span, distance), expected_result)

    @data(
        ([], 1.),
        ([1], 1.),
        (1, 1.)
    )
    @unpack
    def test_shift_raises_with_wrong_span_type(self, span, dist):
        with self.assertRaises(TypeError):
            span_utils.shift(span, dist)

    @data(
        ([], 1.),
        ([1], 1.),
        (1, 1.),
        ([1., 1.], None),
        ([1., 1.], [1.]),
        ([1., 1.], [1., 1.])
    )
    @unpack
    def test_zoom_raises_with_wrong_types(self, span, factor):
        with self.assertRaises(TypeError):
            span_utils.zoom(span, factor)


class SpanMergeTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_merging_zero_span_gives_zero_span(self):
        self.assertEqual(span_utils.merge([]), [])

    def test_merging_two_disjoin_spans_preserves_input(self):
        self.assertEqual(span_utils.merge([[1, 2], [4, 5]]), [[1, 2], [4, 5]])

    def test_merging_two_overlapping_spans_merges_them(self):
        self.assertEqual(span_utils.merge([[1, 4], [3, 5]]), [[1, 5]])


@ddt
class SpanDiffTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        ([], []),
        ([5, 2], [2, 5]),
        ([2, 5], [5, 2])
    )
    @unpack
    def test_invalid_span_raises(self, span1, span2):
        with self.assertRaises(TypeError):
            span_utils.difference(span1, span2)

    def test_two_identical_spans_have_no_difference(self):
        self.assertEqual(span_utils.difference([1, 2], [1, 2]), [])

    def test_left_overlapping_spans_have_one_different_chunk(self):
        '''
        ----------++++++++++++++++++++--------
        ++++++++++++++++++++------------------
        --------------------++++++++++--------
        '''
        self.assertEqual(span_utils.difference([10, 30], [0, 20]), [[20, 30]])

    def test_right_overlapping_spans_have_one_different_chunk(self):
        '''
        ----------++++++++++++++++++++--------
        ------------------++++++++++++++++++++
        ----------++++++++--------------------
        '''
        self.assertEqual(span_utils.difference([10, 30], [20, 40]), [[10, 20]])

    def test_span_minus_centered_smaller_span_gives_two_different_chunks(self):
        '''
        ++++++++++++++++++++++++++++++++++++++
        ---------+++++++++++++++++++----------
        +++++++++-------------------++++++++++
        '''
        self.assertEqual(span_utils.difference([0, 40], [20, 30]), [[0, 20], [30, 40]])

    def test_span_minus_non_overlapping_gives_span(self):
        '''
        -------------------+++++++++++++++++++
        ++++++++++++++++++--------------------
        -------------------+++++++++++++++++++
        '''
        self.assertEqual(span_utils.difference([20, 40], [0, 19]), [[20, 40]])
        '''
        +++++++++++++++++++-------------------
        --------------------++++++++++++++++++
        -------------------+++++++++++++++++++
        '''
        self.assertEqual(span_utils.difference([0, 20], [21, 40]), [[0, 20]])


@ddt
class _DateTimeRangeTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        (
            DateTimeRange(datetime(2001, 1, 8, 1, 0, 0), datetime(2001, 1, 8, 2, 0, 0)),
            DateTimeRange(datetime(2001, 1, 8, 0, 0, 0), datetime(2001, 1, 8, 3, 0, 0)),
            []
        ),
        (
            DateTimeRange(datetime(2002, 1, 8, 1, 0, 0), datetime(2002, 1, 8, 2, 0, 0)),
            DateTimeRange(datetime(2002, 1, 8, 1, 0, 0), datetime(2002, 1, 8, 2, 0, 0)),
            []
        ),
        (
            DateTimeRange(datetime(2003, 1, 8, 0, 0, 0), datetime(2003, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2003, 1, 8, 1, 0, 0), datetime(2003, 1, 8, 2, 0, 0)),
            [
                DateTimeRange(datetime(2003, 1, 8, 0, 0, 0), datetime(2003, 1, 8, 1, 0, 0)),
                DateTimeRange(datetime(2003, 1, 8, 2, 0, 0), datetime(2003, 1, 8, 4, 0, 0)),
            ]
        ),
        (
            DateTimeRange(datetime(2004, 1, 8, 0, 0, 0), datetime(2004, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2004, 1, 8, 3, 0, 0), datetime(2004, 1, 8, 5, 0, 0)),
            [
                DateTimeRange(datetime(2004, 1, 8, 0, 0, 0), datetime(2004, 1, 8, 3, 0, 0))
            ]
        ),
        (
            DateTimeRange(datetime(2005, 1, 8, 2, 0, 0), datetime(2005, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2005, 1, 8, 0, 0, 0), datetime(2005, 1, 8, 3, 0, 0)),
            [
                DateTimeRange(datetime(2005, 1, 8, 3, 0, 0), datetime(2005, 1, 8, 4, 0, 0))
            ]
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0))
            ]
        )
    )
    @unpack
    def test_range_diff(self, range1, range2, expected):
        self.assertEqual(range1 - range2, expected)

    def test_range_substract_timedelta(self):
        self.assertEqual(
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0))
            -
            timedelta(hours=1),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)))

    def test_add_with_wrong_type(self):
        with self.assertRaises(TypeError):
            DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 4, 0, 0)) + 1

    def test_substract_with_wrong_type(self):
        with self.assertRaises(TypeError):
            DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 4, 0, 0)) - 1

    @data(
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0), datetime(2000, 1, 1, 1, 0, 0)),
            1.,
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0), datetime(2000, 1, 1, 1, 0, 0))
        ),
        (
            DateTimeRange(datetime(2000, 1, 1, 1, 0, 0), datetime(2000, 1, 1, 2, 0, 0)),
            2.,
            DateTimeRange(datetime(2000, 1, 1, 0, 30, 0), datetime(2000, 1, 1, 2, 30, 0))
        ),
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 30, 0), datetime(2000, 1, 1, 2, 30, 0)),
            .5,
            DateTimeRange(datetime(2000, 1, 1, 1, 0, 0), datetime(2000, 1, 1, 2, 0, 0))
        )
    )
    @unpack
    def test_scale(self, dt_range, factor, expected):
        self.assertEqual(dt_range * factor, expected)

    @data(
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 1, 0, 0, tzinfo=timezone.utc)),
            1,
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 1, 0, 0, tzinfo=timezone.utc))
        ),
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 0, 0, 2, tzinfo=timezone.utc)),
            1,
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 1, 0, 0, tzinfo=timezone.utc))
        ),
        (
            DateTimeRange(datetime(2000, 1, 1, 3, 30, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 5, 30, 0, tzinfo=timezone.utc)),
            12,
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        ),
    )
    @unpack
    def test_range_rounding(self, dt_range, fragment_hours, expected):
        self.assertEqual(_round_for_cache(dt_range, fragment_hours), expected)

    @data(
        (DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                       datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)),
         DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                       datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)),
         operator.eq
         ),
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)),
            DateTimeRange(datetime(2000, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 2, 0, 0, tzinfo=timezone.utc)),
            operator.contains
        )
        ,
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)),
            (datetime(2000, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
             datetime(2000, 1, 1, 2, 0, 0, tzinfo=timezone.utc)),
            operator.contains
        )
    )
    @unpack
    def test_comparaisons(self, range1, range2, op):
        self.assertTrue(op(range1, range2))


if __name__ == '__main__':
    unittest.main()
