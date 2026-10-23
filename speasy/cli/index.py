from typing import Optional

from cyclopts import App

from ._common import console, table
from .data import TimeRanges, collect_ranges, fetch_all

app = App(name='index', help="Fill and inspect a persistent data index, see speasy.DataIndex.")


def _open(path: str):
    from speasy.data_index import DataIndex
    return DataIndex(path)


def _spans(spans) -> str:
    return ', '.join(f"{start:%Y-%m-%d} → {stop:%Y-%m-%d}" for start, stop in spans) or '-'


@app.command
def fill(path: str, *products: str, time_ranges: TimeRanges = None, ranges_file: Optional[str] = None,
         ranges_from: Optional[str] = None, workers: int = 1) -> int:
    """Download products into the data index at PATH, created if needed, to use them later from Python.

    Parameters
    ----------
    path: str
        The data index folder.
    products: str
        Product paths, e.g. 'amda/imf' 'cda/AC_H0_MFI/BGSEc'.
    time_ranges: Optional[List[Tuple[str, str]]]
        A START STOP time range, repeat it for several ranges.
    ranges_file: Optional[str]
        A file with one 'START STOP' range per line ('#' starts a comment).
    ranges_from: Optional[str]
        A timetable or catalog product, e.g. an AMDA shared timetable: one range per event.
    workers: int
        How many requests run at the same time.
    """
    ranges = collect_ranges(time_ranges, ranges_file, ranges_from)
    with _open(path) as index:
        return fetch_all(index.get_data, products, ranges, workers)


@app.command
def info(path: str) -> int:
    """Print what the data index at PATH holds: per product, the days with data and those known to hold none."""
    import humanize
    from speasy.data_index import FORMAT
    with _open(path) as index:
        console().print(table('', '', rows=[('path', index.path), ('size', humanize.naturalsize(index.disk_size())),
                                            ('format', str(FORMAT))]))
        rows = [(entry['product'], ', '.join(f"{k}={v}" for k, v in entry['options'].items()) or '-',
                 _spans(entry['data']), _spans(entry['empty'])) for entry in index.summary()]
        console().print(table('product', 'options', 'data', 'known empty', rows=rows))
    return 0


@app.command(name='export')
def export_data(path: str, tar: str) -> int:
    """Write the data index at PATH to the TAR file, to import it elsewhere."""
    with _open(path) as index:
        index.export_data(tar)
    console().print(f"exported {path} to {tar}", highlight=False)
    return 0


@app.command(name='import')
def import_data(path: str, source: str) -> int:
    """Add what SOURCE, a tar from 'speasy index export' or an index folder, holds to the data index at PATH."""
    with _open(path) as index:
        index.import_data(source)
    console().print(f"imported {source} into {path}", highlight=False)
    return 0
