"""File reader for table-patched products, plugged into the direct archive downloader in place of `_read_cdf`."""
from datetime import timedelta
from typing import Optional

import pycdfpp

from speasy.core.any_files import any_loc_open
from speasy.core.cache import CacheCall
from speasy.core.direct_archive_downloader.direct_archive_downloader import FileLoaderCallable
from speasy.products import SpeasyVariable

from .decoders import Decoder
from .table import PatchedParameter, is_injected


def _load(url: str) -> pycdfpp.CDF:
    with any_loc_open(url, mode='rb', cache_remote_files=True) as f:
        return pycdfpp.load(f.read())


def _how_to_fix(dataset: str, error: Exception) -> str:
    if isinstance(error, OSError):
        return "Retry later."
    if is_injected(dataset):
        return "This file can't be decoded, please report it to the speasy developers."
    return "Use method='API' to get CDAWeb's web-service version (bucketed shape), and report it to the speasy developers."


# Its own cache rather than _read_cdf's, so a flat result is never mixed with an old bucketed one.
# The decoder is part of the key: editing a table entry must not serve results decoded the old way.
@CacheCall(cache_retention=timedelta(hours=12), is_pure=True)
def _read_patched(url: str, dataset: str, variable: str, decoder: Decoder) -> Optional[SpeasyVariable]:
    try:
        return decoder.decode(_load(url), variable)
    except Exception as e:
        raise (OSError if isinstance(e, OSError) else ValueError)(
            f"{dataset}, file {url}: {e}. {_how_to_fix(dataset, e)}") from e


def patched_reader(entry: PatchedParameter) -> FileLoaderCallable:
    def read(url: Optional[str], variable: str, **kwargs) -> Optional[SpeasyVariable]:
        if url is None:
            return None
        return _read_patched(url, entry.dataset, entry.variable, entry.decoder, **kwargs)

    return read
