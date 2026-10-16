import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, List, Optional, Tuple

from cyclopts import App, Parameter

from ._common import console, error, table

cache_app = App(name='cache', help="Inspect Speasy's local cache.")

_CODEC_EXTENSIONS = ('.cdf', '.nc')


def _save_with_codec(extension: str):
    from speasy.core.codecs import get_codec
    codec = get_codec(extension[1:])
    return codec and (lambda var, path: codec.save_variables([var], file=path))


def _writers() -> dict:
    """Output file extension -> writer(var, path); NetCDF only when its optional codec is installed."""
    codec_writers = {ext: _save_with_codec(ext) for ext in _CODEC_EXTENSIONS}
    return {'.csv': lambda var, path: var.to_dataframe().to_csv(path),
            **{ext: w for ext, w in codec_writers.items() if w}}


def _summary(var) -> list:
    return [('name', var.name), ('shape', str(var.values.shape)), ('unit', str(var.unit)),
            ('start', str(var.time[0]) if len(var) else '-'), ('stop', str(var.time[-1]) if len(var) else '-')]


def get(product: str, start: str, stop: str, *, output: Optional[str] = None) -> int:
    """Download a product, print a summary or save it to a file.

    Parameters
    ----------
    product: str
        Product path, e.g. 'amda/imf' or 'cda/AC_H0_MFI/BGSEc'.
    start: str
        Start time, e.g. 2018-06-01.
    stop: str
        Stop time.
    output: Optional[str]
        Save to this file, the extension picks the format (.cdf, .csv, .nc).
    """
    import speasy
    writers = _writers()
    extension = os.path.splitext(output)[1].lower() if output else None
    if output and extension not in writers:
        return error(f"can't write '{extension}' files, supported formats are: {', '.join(sorted(writers))}")
    var = speasy.get_data(product, start, stop)
    if var is None:
        return error(f"no data for {product} between {start} and {stop}")
    if output:
        writers[extension](var, output)
    console().print(table('', '', rows=_summary(var)))
    return 0


def _read_ranges(path: str) -> List[Tuple[str, str]]:
    """One 'start stop' (or 'start,stop') range per line; blank lines and '#' comments are skipped."""
    ranges = []
    with open(path) as f:
        for number, line in enumerate(f, start=1):
            fields = line.split('#')[0].replace(',', ' ').split()
            if not fields:
                continue
            if len(fields) != 2:
                raise ValueError(f"{path} line {number}: expected 'START STOP', got '{line.strip()}'")
            ranges.append((fields[0], fields[1]))
    return ranges


def _ranges_from(product: str) -> List[Tuple[str, str]]:
    import speasy
    from speasy.products import Catalog, TimeTable
    needed = "it needs a timetable or a catalog"
    try:
        events = speasy.get_data(product)  # without a time range, speasy only looks for timetables and catalogs
    except ValueError as e:
        raise ValueError(f"--ranges-from {product}: {e}, {needed}") from e
    if not isinstance(events, (TimeTable, Catalog)):
        raise ValueError(f"--ranges-from {product}: gives a {type(events).__name__}, {needed}")
    return [(r.start_time.isoformat(), r.stop_time.isoformat()) for r in events]


def _warm_one(product: str, start: str, stop: str) -> Tuple[bool, str]:
    import speasy
    try:
        var = speasy.get_data(product, start, stop)
    except Exception as e:  # one failing request must not stop the warm-up
        return False, f"[red]✗[/red] {product} {start} → {stop}: {type(e).__name__}: {e}"
    found = f"{len(var)} samples" if var is not None else "no data"
    return True, f"[green]✓[/green] {product} {start} → {stop} ({found})"


@cache_app.command
def warm(*products: str,
         time_ranges: Annotated[Optional[List[Tuple[str, str]]], Parameter(name='--range', negative=())] = None,
         ranges_file: Optional[str] = None, ranges_from: Optional[str] = None, workers: int = 1) -> int:
    """Download products ahead of time, so later requests are served from the cache.

    Parameters
    ----------
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
    ranges = [*(time_ranges or []), *(_read_ranges(ranges_file) if ranges_file else []),
              *(_ranges_from(ranges_from) if ranges_from else [])]
    if not ranges:
        return error("give at least one time range, with --range START STOP, --ranges-file FILE "
                     "or --ranges-from TIMETABLE")
    if workers < 1:
        return error(f"--workers must be at least 1, got {workers}")
    # threads, not processes: a process pool deadlocks on Speasy's import lock (#381)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_warm_one, product, start, stop) for product in products for start, stop in ranges]
        results = []
        for future in as_completed(futures):  # printed from this thread only, lines never interleave
            ok, line = future.result()
            console().print(line, highlight=False)
            results.append(ok)
    console().print(f"{sum(results)}/{len(results)} requests done")
    return 0 if all(results) else 1


@cache_app.command
def info() -> int:
    """Print where the cache lives, its size and how many entries it holds."""
    import humanize
    from speasy.config import cache as cache_cfg
    from speasy.core.cache import cache_len, cache_disk_size
    rows = [('path', cache_cfg.path.get()), ('size', humanize.naturalsize(cache_disk_size())),
            ('entries', str(cache_len()))]
    console().print(table('', '', rows=rows))
    return 0
