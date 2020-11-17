import unittest
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.common.datetime_range import DateTimeRange, span_difference
from spwc.cache import _round_for_cache
import operator


@ddt
class SpanDiffTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        ([],[]),
        ([5,2],[2,5]),
        ([2,5],[5,2])
    )
    @unpack
    def test_invalid_span_raises(self, span1, span2):
        with self.assertRaises(AssertionError):
            span_difference(span1, span2)

    def test_two_identical_spans_have_no_difference(self):
        self.assertEqual(span_difference([1,2],[1,2]), [])

    def test_left_overlapping_spans_have_one_different_chunk(self):
        '''
        ----------++++++++++++++++++++--------
        ++++++++++++++++++++------------------
        --------------------++++++++++--------
        '''
        self.assertEqual(span_difference([10, 30], [0, 20]), [[20,30]])

    def test_right_overlapping_spans_have_one_different_chunk(self):
        '''
        ----------++++++++++++++++++++--------
        ------------------++++++++++++++++++++
        ----------++++++++--------------------
        '''
        self.assertEqual(span_difference([10, 30], [20, 40]), [[10,20]])

    def test_span_minus_centered_smaller_span_gives_two_different_chunks(self):
        '''
        ++++++++++++++++++++++++++++++++++++++
        ---------+++++++++++++++++++----------
        +++++++++-------------------++++++++++
        '''
        self.assertEqual(span_difference([0, 40], [20, 30]), [[0, 20],[30,40]])


@ddt
class _DateTimeRangeTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        (
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 3, 0, 0)),
            []
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0)),
            []
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)),
                DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            ]
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 5, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 3, 0, 0))
            ]
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 3, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 4, 0, 0))
            ]
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0))
            ]
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)),
                DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 3, 30, 0))
            ],
            [
                DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 3, 0, 0)),
                DateTimeRange(datetime(2006, 1, 8, 3, 30, 0), datetime(2006, 1, 8, 4, 0, 0))
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
