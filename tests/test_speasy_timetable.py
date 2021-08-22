import unittest
from datetime import datetime

from speasy.products.timetable import TimeTable
from speasy.core.datetime_range import DateTimeRange


class SpeasyTimetable(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_len_equals_number_of_ranges_inserted(self):
        tt = TimeTable("Empty TimeTable")
        self.assertEqual(len(tt), 0)
        tt.append(DateTimeRange(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(tt), 1)
        for _ in range(9):
            tt.append(DateTimeRange(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(tt), 10)

    def test_raises_if_non_ranges_types_are_appended(self):
        tt = TimeTable("Empty TimeTable")
        with self.assertRaises(TypeError):
            tt.append("this is not a DateTimeRange")

    def test_raises_if_built_with_non_ranges_types(self):
        with self.assertRaises(TypeError):
            tt = TimeTable("Failing TimeTable", dt_ranges="this is not a DateTimeRange")

    def test_holds_given_metadata(self):
        meta = {'key': 10}
        tt = TimeTable("TimeTable with metadata", meta=meta)
        self.assertEqual(meta, tt.meta)


class AnEmptySpeasyTimetable(unittest.TestCase):
    def setUp(self):
        self.tt = TimeTable("Empty timetable")

    def tearDown(self):
        pass

    def test_1_has_a_len_equal_to_0(self):
        self.assertEqual(len(self.tt), 0)

    def test_2_can_append_dt_range(self):
        self.tt.append(DateTimeRange(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(self.tt), 1)
        self.tt += DateTimeRange(start_time=datetime.now(), stop_time=datetime.now())
        self.assertEqual(len(self.tt), 2)

    def test_3_can_append_dt_range_list(self):
        sz = len(self.tt)
        self.tt.append([DateTimeRange(start_time=datetime.now(), stop_time=datetime.now())] * 10)
        self.assertEqual(len(self.tt), sz + 10)
        self.tt += [DateTimeRange(start_time=datetime.now(), stop_time=datetime.now())] * 10
        self.assertEqual(len(self.tt), sz + 20)


class ANonEmptySpeasyTimetable(unittest.TestCase):
    def setUp(self):
        self.tt = TimeTable("Non empty timetable")
        for _ in range(10):
            self.tt.append(DateTimeRange(start_time=datetime.now(), stop_time=datetime.now()))

    def tearDown(self):
        pass

    def test_has_a_len_different_from_0(self):
        self.assertNotEqual(len(self.tt), 0)

    def test_can_be_indexed(self):
        self.assertIs(type(self.tt[-1]), DateTimeRange)
        self.assertIs(type(self.tt[:]), list)

    def test_can_append_dt_ranges(self):
        prev_len = len(self.tt)
        self.tt.append(DateTimeRange(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(self.tt), prev_len + 1)

    def test_can_pop_dt_ranges(self):
        prev_len = len(self.tt)
        self.tt.append(DateTimeRange(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(self.tt), prev_len + 1)
        self.tt.pop(-1)
        self.assertEqual(len(self.tt), prev_len)
