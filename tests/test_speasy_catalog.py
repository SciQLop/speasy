import unittest
from datetime import datetime

from speasy.common.catalog import Catalog, Event


class SpeasyCatalog(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_len_equals_number_of_ranges_inserted(self):
        cat = Catalog("Empty Catalog")
        self.assertEqual(len(cat), 0)
        cat.append(Event(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(cat), 1)
        for _ in range(9):
            cat.append(Event(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(cat), 10)

    def test_raises_if_non_ranges_types_are_appended(self):
        cat = Catalog("Empty Catalog")
        with self.assertRaises(TypeError):
            cat.append("this is not an Event")

    def test_raises_if_built_with_non_ranges_types(self):
        with self.assertRaises(TypeError):
            cat = Catalog("Failing Catalog", events="this is not a Event")

    def test_holds_given_metadata(self):
        meta = {'key': 10}
        cat = Catalog("Catalog with metadata", meta=meta)
        self.assertEqual(meta, cat.meta)


class AnEmptySpeasyCatalog(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog("Empty Catalog")

    def tearDown(self):
        pass

    def test_1_has_a_len_equal_to_0(self):
        self.assertEqual(len(self.cat), 0)

    def test_2_can_append_dt_range(self):
        self.cat.append(Event(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(self.cat), 1)
        self.cat += Event(start_time=datetime.now(), stop_time=datetime.now())
        self.assertEqual(len(self.cat), 2)

    def test_3_can_append_dt_range_list(self):
        sz = len(self.cat)
        self.cat.append([Event(start_time=datetime.now(), stop_time=datetime.now())] * 10)
        self.assertEqual(len(self.cat), sz + 10)
        self.cat += [Event(start_time=datetime.now(), stop_time=datetime.now())] * 10
        self.assertEqual(len(self.cat), sz + 20)


class ANonEmptySpeasyCatalog(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog("Non empty Catalog")
        for _ in range(10):
            self.cat.append(Event(start_time=datetime.now(), stop_time=datetime.now()))

    def tearDown(self):
        pass

    def test_has_a_len_different_from_0(self):
        self.assertNotEqual(len(self.cat), 0)

    def test_can_be_indexed(self):
        self.assertIs(type(self.cat[-1]), Event)
        self.assertIs(type(self.cat[:]), list)

    def test_can_append_dt_ranges(self):
        prev_len = len(self.cat)
        self.cat.append(Event(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(self.cat), prev_len + 1)

    def test_can_pop_dt_ranges(self):
        prev_len = len(self.cat)
        self.cat.append(Event(start_time=datetime.now(), stop_time=datetime.now()))
        self.assertEqual(len(self.cat), prev_len + 1)
        self.cat.pop(-1)
        self.assertEqual(len(self.cat), prev_len)
