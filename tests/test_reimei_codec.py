import os
import unittest

import numpy as np

import speasy

from speasy.core.codecs import get_codec

_CHANNELS = [(f"{ch:02d}", 999.99, 0.0) for ch in range(4)] + \
            [(f"{ch:02d}", 150.0 - 10 * ch, 0.1) for ch in range(4, 26)] + \
            [(f"{ch:02d}", 999.99, 0.0) for ch in range(26, 31)] + [("31", -12.18, 1.067106)]
_EMPTY_STEPS = ("01", "11")


def _energy_rows():
    rows = []
    for step in range(32):
        name = f"{step:02x}"
        values = f"{1000.0 + step:8.1f}    0.50 {1100.0 + step:8.1f} {900.0 + step:8.1f}"
        rows.append(name if name in _EMPTY_STEPS else f"{name} {values}")
    return rows


HEADER = "\n".join([
    "###CALFILE", "esaGfac_from_calcG060731.txt", "###CALDATA", "Sensitivities and efficiencies of INDEX/ESA  060731",
    "", "J = C / ( effi * Gfac * K * dt )", "dt:    0.001232 [s]", "",
    "CH  Az[deg] Gfac(*1000) ", *[f"{ch}  {az:7.2f}   {g:.6f}" for ch, az, g in _CHANNELS], "",
    "Energy steps", "Step Energy Efficiency EnergyH EnergyL", *_energy_rows(), "",
    "###FORMAT", "yyyymmdd hh:mm:ss.ssss titititi",
    "total gomi ch00 01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  "
    "25  26  27  28  29",
    "unit: counts", "###DATA", ""])


def _block(time: str, sweep: int) -> str:
    rows = [" ".join(str(sweep * 10000 + step * 100 + col) for col in range(32)) for step in range(32)]
    return "\n".join([f"{time} 17a12cc1", *rows]) + "\n"


def l2_file(*times: str, truncated_tail: bool = False) -> bytes:
    content = HEADER + "".join(_block(time, sweep) for sweep, time in enumerate(times))
    if truncated_tail:
        content += "20080229 11:14:27.3897 17a12cc3\n" + "1 2 3\n"
    return content.encode()


def load(content: bytes, name: str):
    return get_codec("reimei/l2").load_variable(variable=name, file=content)


TWO_SWEEPS = l2_file("20080229 11:14:27.3097", "20080229 11:14:27.3497")


class ReimeiL2Codec(unittest.TestCase):
    def test_counts_are_time_by_energy_by_channel(self):
        counts = load(TWO_SWEEPS, "counts")
        self.assertEqual(counts.values.shape, (2, 32, 30))
        np.testing.assert_array_equal(counts.time, np.array(["2008-02-29T11:14:27.3097", "2008-02-29T11:14:27.3497"],
                                                            dtype="datetime64[ns]"))
        self.assertEqual(counts.values[1, 3, 0], 10000 + 300 + 2)   # ch00 is the third column, after total and gomi
        self.assertEqual(counts.unit, "counts")

    def test_energy_axis_comes_from_the_header_with_the_ramping_steps_empty(self):
        energy = load(TWO_SWEEPS, "counts").axes[1]
        self.assertEqual(energy.values.shape, (32,))
        self.assertEqual(energy.values[2], 1002.0)
        self.assertTrue(np.isnan(energy.values[[0x01, 0x11]]).all())
        self.assertEqual(energy.unit, "eV")
        self.assertFalse(energy.is_time_dependent)

    def test_channel_axis_is_the_azimuth_with_invalid_channels_empty(self):
        azimuth = load(TWO_SWEEPS, "counts").axes[2]
        self.assertEqual(azimuth.values.shape, (30,))
        self.assertEqual(azimuth.values[4], 110.0)
        self.assertTrue(np.isnan(azimuth.values[[0, 3, 26, 29]]).all())
        self.assertEqual(azimuth.unit, "deg")

    def test_total_and_gomi_are_their_own_variables(self):
        total, gomi = load(TWO_SWEEPS, "total"), load(TWO_SWEEPS, "gomi")
        self.assertEqual(total.values.shape, (2, 32))
        self.assertEqual(total.values[1, 3], 10000 + 300)
        self.assertEqual(gomi.values[1, 3], 10000 + 300 + 1)

    def test_a_truncated_last_sweep_is_dropped(self):
        counts = load(l2_file("20080229 11:14:27.3097", truncated_tail=True), "counts")
        self.assertEqual(counts.values.shape, (1, 32, 30))

    def test_lists_its_variables(self):
        self.assertListEqual(get_codec("reimei/l2").list_variables(TWO_SWEEPS), ["counts", "total", "gomi"])

    def test_unknown_variable_gives_none(self):
        self.assertIsNone(load(TWO_SWEEPS, "flux"))

    def test_not_a_reimei_file_says_what_is_missing(self):
        with self.assertRaisesRegex(ValueError, "not a REIMEI Level-2 ESA/ISA file.*###DATA"):
            load(b"just some text\n", "counts")


class ReimeiL2FromDarts(unittest.TestCase):
    def test_reads_a_real_esa_file(self):
        url = "https://data.darts.isas.jaxa.jp/pub/reimei/Level-2/2008/03/RE_ESA_20080229111427.L2"
        counts = get_codec("reimei/l2").load_variable(variable="counts", file=url)
        self.assertEqual(counts.values.shape, (3628, 32, 30))
        self.assertEqual(counts.time[0], np.datetime64("2008-02-29T11:14:27.3097", "ns"))
        self.assertEqual(counts.axes[1].values[2], 11400.0)
        self.assertEqual(counts.axes[2].values[4], 148.84)


class ReimeiArchiveNodes(unittest.TestCase):
    """SciQLop picks a spectrogram from the node's DISPLAY_TYPE (ISTP). The archive also copies it into the data."""

    def setUp(self):
        from speasy.core.inventory.indexes import SpeasyIndex
        from speasy.data_providers.generic_archive import load_inventory_file
        self.root = SpeasyIndex(name='archive', provider='archive', uid='')
        load_inventory_file(os.path.join(os.path.dirname(speasy.__file__), 'data', 'archive', 'reimei.yaml'), self.root)

    def test_energy_spectra_are_spectrograms(self):
        for instrument in ("esa_l2", "isa_l2"):
            for name in ("total", "gomi"):
                with self.subTest(instrument=instrument, name=name):
                    node = getattr(getattr(self.root.darts.REIMEI, instrument), name)
                    self.assertEqual(node.DISPLAY_TYPE, "spectrogram")

    def test_the_3d_distribution_has_no_display_type(self):
        # time x energy x channel: a spectrogram only after a reduction over one of its axes.
        for instrument in ("esa_l2", "isa_l2"):
            with self.subTest(instrument=instrument):
                self.assertNotIn("DISPLAY_TYPE", getattr(self.root.darts.REIMEI, instrument).counts.__dict__)


class ReimeiInTheArchive(unittest.TestCase):
    def test_a_month_end_pass_filed_in_the_next_month_folder_is_found(self):
        import speasy as spz
        for instrument in ("esa_l2", "isa_l2"):
            with self.subTest(instrument=instrument):
                counts = spz.get_data(f"archive/darts/REIMEI/{instrument}/counts", "2008-02-29T11:15",
                                      "2008-02-29T11:16")
                self.assertIsNotNone(counts)
                self.assertEqual(counts.values.shape[1:], (32, 30))
                self.assertGreaterEqual(counts.time[0], np.datetime64("2008-02-29T11:15", "ns"))
                self.assertIn("DARTS", counts.meta["Acknowledgement"])


if __name__ == "__main__":
    unittest.main()
