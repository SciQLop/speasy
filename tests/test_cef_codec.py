import gzip
import io
import os
import tempfile
import unittest

import numpy as np

from speasy.core.codecs import get_codec

HEADER = '''FILE_NAME = "test.cef"
FILE_FORMAT_VERSION = "CEF-2.0"
END_OF_RECORD_MARKER = "$"
'''

TIME = '''START_VARIABLE = time_tags
  VALUE_TYPE = ISO_TIME
  UNITS = "s"
  FILLVAL = 9999-12-31T23:59:59Z
  PARAMETER_TYPE = "Support_Data"
END_VARIABLE = time_tags
'''


def variable(name, value_type="FLOAT", sizes=None, data=None, **attributes):
    lines = [f"START_VARIABLE = {name}", f"  VALUE_TYPE = {value_type}"]
    lines += [f"  SIZES = {sizes}"] if sizes else []
    lines += [f"  {key} = {value}" for key, value in attributes.items()]
    lines += [f"  DATA = {data}"] if data else []
    return "\n".join(lines + [f"END_VARIABLE = {name}", ""])


def cef(variables, records, time=TIME):
    return (HEADER + time + "".join(variables) + "DATA_UNTIL = EOF\n"
            + "".join(f"{record} $\n" for record in records)).encode()


def load(content, name):
    return get_codec("cef").load_variable(variable=name, file=content)


SCALAR = cef([variable("density", UNITS='"cm^-3"', FILLVAL="-1.0E31", DEPEND_0="time_tags",
                       PARAMETER_TYPE='"Data"', DISPLAYTYPE='"time_series"', SI_CONVERSION='"1.0e6>m^-3"',
                       CATDESC='"Ion density"', FIELDNAM='"Density"', LABLAXIS='"N"')],
             ["2005-06-10T00:00:00Z, 3.5", "2005-06-10T00:00:04Z, -1.0E31", "2005-06-10T00:00:08Z, 3.7"])


def vector(**attributes):
    return cef([variable("B", sizes=3, UNITS='"nT"', DEPEND_0="time_tags", **attributes)],
               ["2005-06-10T00:00:00Z, 1, 2, 3", "2005-06-10T00:00:04Z, 4, 5, 6"])


class CefScalar(unittest.TestCase):
    def setUp(self):
        self.v = load(SCALAR, "density")

    def test_values_and_time(self):
        self.assertEqual(self.v.values.shape, (3, 1))
        self.assertEqual(self.v.time[1], np.datetime64("2005-06-10T00:00:04", "ns"))
        self.assertEqual(self.v.values[0, 0], np.float32(3.5))

    def test_fill_values_are_kept_and_declared(self):
        self.assertEqual(self.v.values[1, 0], np.float32(-1e31))
        self.assertEqual(self.v.fill_value, np.float32(-1e31))
        self.assertTrue(np.isnan(self.v.replace_fillval_by_nan().values[1, 0]))

    def test_attributes_are_kept(self):
        self.assertEqual(self.v.unit, "cm^-3")
        self.assertEqual(self.v.meta["CATDESC"], "Ion density")
        self.assertEqual(self.v.meta["DEPEND_0"], "time_tags")

    def test_cef_attributes_are_also_given_their_istp_names(self):
        self.assertEqual(self.v.meta["DISPLAY_TYPE"], "time_series")
        self.assertEqual(self.v.meta["VAR_TYPE"], "data")
        self.assertEqual(self.v.meta["SI_conversion"], "1.0e6>m^-3")
        self.assertEqual(self.v.meta["DISPLAYTYPE"], "time_series")

    def test_time_axis_keeps_its_attributes(self):
        self.assertEqual(self.v.axes[0].meta["UNITS"], "s")
        self.assertEqual(self.v.axes[0].name, "time")  # same name as the ISTP codec gives

    def test_name(self):
        self.assertEqual(self.v.name, "density")


class CefColumns(unittest.TestCase):
    def test_label_1_list(self):
        self.assertListEqual(load(vector(LABEL_1='"Bx", "By", "Bz"'), "B").columns, ["Bx", "By", "Bz"])

    def test_label_1_naming_a_variable(self):
        content = cef([variable("B", sizes=3, DEPEND_0="time_tags", LABEL_1="B_labels"),
                       variable("B_labels", value_type="CHAR", sizes=3, data='"x", "y", "z"')],
                      ["2005-06-10T00:00:00Z, 1, 2, 3"])
        self.assertListEqual(load(content, "B").columns, ["x", "y", "z"])

    def test_representation_1_when_there_is_no_label(self):
        self.assertListEqual(load(vector(REPRESENTATION_1='"x", "y", "z"'), "B").columns, ["x", "y", "z"])

    def test_numbered_components_when_nothing_names_them(self):
        self.assertListEqual(load(vector(), "B").columns, ["component_0", "component_1", "component_2"])

    def test_a_single_value_is_named_by_its_axis_label(self):
        self.assertListEqual(load(SCALAR, "density").columns, ["N"])

    def test_a_single_value_without_axis_label_is_named_after_the_variable(self):
        content = cef([variable("density", DEPEND_0="time_tags")], ["2005-06-10T00:00:00Z, 3.5"])
        self.assertListEqual(load(content, "density").columns, ["density"])

    def test_multidimensional_values_are_named_like_a_single_value(self):
        self.assertListEqual(load(SPECTRO, "flux").columns, ["flux"])

    def test_labels_of_the_wrong_length_are_ignored(self):
        self.assertListEqual(load(vector(LABEL_1='"Bx", "By"'), "B").columns,
                             ["component_0", "component_1", "component_2"])


SPECTRO = cef([variable("pitch", sizes=2, data="45, 135", UNITS='"deg"'),
               variable("energy", sizes=3, DEPEND_0="time_tags", UNITS='"eV"'),
               variable("flux", sizes="2, 3", DEPEND_0="time_tags", DEPEND_1="pitch", DEPEND_2="energy",
                        DISPLAYTYPE='"spectrogram"', UNITS='"keV/cm^2-s-str-keV"')],
              ["2005-06-10T00:00:00Z, 10, 100, 1000, 1, 2, 3, 4, 5, 6",
               "2005-06-10T00:00:04Z, 20, 200, 2000, 7, 8, 9, 10, 11, 12"])


class CefAxes(unittest.TestCase):
    def setUp(self):
        self.v = load(SPECTRO, "flux")

    def test_values_keep_their_shape(self):
        self.assertEqual(self.v.values.shape, (2, 2, 3))
        self.assertEqual(self.v.values[1, 1, 2], 12)

    def test_fixed_depend_is_a_time_independent_axis(self):
        pitch = self.v.axes[1]
        self.assertEqual(pitch.name, "pitch")
        self.assertFalse(pitch.is_time_dependent)
        self.assertListEqual(pitch.values.tolist(), [45, 135])
        self.assertEqual(pitch.meta["UNITS"], "deg")

    def test_record_varying_depend_is_a_time_dependent_axis(self):
        energy = self.v.axes[2]
        self.assertTrue(energy.is_time_dependent)
        self.assertListEqual(energy.values[1].tolist(), [20, 200, 2000])

    def test_a_missing_depend_before_a_later_one_gets_an_index_axis(self):
        content = cef([variable("energy", sizes=3, data="10, 100, 1000"),
                       variable("flux", sizes="2, 3", DEPEND_0="time_tags", DEPEND_2="energy")],
                      ["2005-06-10T00:00:00Z, 1, 2, 3, 4, 5, 6"])
        v = load(content, "flux")
        self.assertListEqual(v.axes[1].values.tolist(), [0, 1])
        self.assertListEqual(v.axes[2].values.tolist(), [10, 100, 1000])

    def test_no_axis_for_trailing_dimensions_without_depend(self):
        self.assertEqual(len(load(vector(), "B").axes), 1)


class CefTime(unittest.TestCase):
    def test_records_without_time_are_dropped(self):
        content = cef([variable("energy", sizes=2, DEPEND_0="time_tags"),
                       variable("flux", sizes=2, DEPEND_0="time_tags", DEPEND_1="energy")],
                      ["2005-06-10T00:00:00Z, 1, 2, 3, 4", "9999-12-31T23:59:59Z, 5, 6, 7, 8",
                       "2005-06-10T00:00:08Z, 9, 10, 11, 12"])
        v = load(content, "flux")
        self.assertEqual(len(v), 2)
        self.assertListEqual(v.values[:, 0].tolist(), [3, 11])
        self.assertListEqual(v.axes[1].values[:, 0].tolist(), [1, 9])

    def test_time_ranges_are_placed_at_their_middle(self):
        time = TIME.replace("ISO_TIME", "ISO_TIME_RANGE").replace(
            "9999-12-31T23:59:59Z", "9999-12-31T23:59:59Z/9999-12-31T23:59:59Z")
        content = cef([variable("count", value_type="INT", DEPEND_0="time_tags")],
                      ["2005-06-10T00:00:00Z/2005-06-10T00:01:00Z, 7"], time=time)
        self.assertEqual(load(content, "count").time[0], np.datetime64("2005-06-10T00:00:30", "ns"))


class CefNothingToReturn(unittest.TestCase):
    def test_no_records(self):
        self.assertIsNone(load(cef([variable("density", DEPEND_0="time_tags")], []), "density"))

    def test_unknown_variable(self):
        self.assertIsNone(load(SCALAR, "not_there"))

    def test_variable_without_time(self):
        self.assertIsNone(load(SPECTRO, "pitch"))

    def test_depend_0_that_is_not_a_time(self):
        content = cef([variable("index", value_type="INT", DEPEND_0="time_tags"),
                       variable("counts", value_type="INT", DEPEND_0="index")], ["2005-06-10T00:00:00Z, 1, 7"])
        self.assertIsNone(load(content, "counts"))

    def test_the_time_variable_itself(self):
        self.assertIsNone(load(SCALAR, "time_tags"))


class CefInputs(unittest.TestCase):
    def test_gzipped_bytes(self):
        self.assertEqual(len(load(gzip.compress(SCALAR), "density")), 3)

    def test_file_like_object(self):
        self.assertEqual(len(load(io.BytesIO(SCALAR), "density")), 3)

    def test_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.cef")
            with open(path, "wb") as f:
                f.write(SCALAR)
            self.assertEqual(len(load(path, "density")), 3)

    def test_several_variables_at_once(self):
        loaded = get_codec("cef").load_variables(variables=["flux", "energy", "pitch"], file=SPECTRO)
        self.assertEqual(loaded["flux"].values.shape, (2, 2, 3))
        self.assertEqual(loaded["energy"].values.shape, (2, 3))
        self.assertIsNone(loaded["pitch"])

    def test_list_variables_gives_the_time_series(self):
        self.assertListEqual(get_codec("cef").list_variables(SPECTRO), ["energy", "flux"])

    def test_invalid_content_says_which_file_and_why(self):
        with self.assertRaisesRegex(ValueError, "Can't read .*CEF"):
            load(b"this is not CEF", "density")


class CefRegistration(unittest.TestCase):
    def test_found_by_name_extension_and_mimetype(self):
        codec = get_codec("cef")
        self.assertIsNotNone(codec)
        self.assertIs(get_codec("application/x-cef"), codec)

    def test_read_only(self):
        with self.assertRaises(NotImplementedError):
            get_codec("cef").save_variables([load(SCALAR, "density")])


if __name__ == '__main__':
    unittest.main()
