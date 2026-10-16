import os
from typing import Optional

from cyclopts import App

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
