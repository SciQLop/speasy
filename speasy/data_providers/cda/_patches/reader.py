"""File reader for table-patched products, plugged into the direct archive downloader in place of `_read_cdf`."""
from datetime import timedelta
from typing import Optional

import pycdfpp

from speasy.core.any_files import any_loc_open
from speasy.core.cache import CacheCall
from speasy.core.direct_archive_downloader.direct_archive_downloader import FileLoaderCallable
from speasy.products import SpeasyVariable

from .table import PatchedParameter, patch_for


def _load(url: str) -> pycdfpp.CDF:
    with any_loc_open(url, mode='rb', cache_remote_files=True) as f:
        return pycdfpp.load(f.read())


# Its own cache rather than _read_cdf's, so a flat result is never mixed with an old bucketed one.
# Keyed on plain strings: the entry's meta dict would make an unstable key.
@CacheCall(cache_retention=timedelta(hours=12), is_pure=True)
def _read_patched(url: str, dataset: str, name: str) -> Optional[SpeasyVariable]:
    entry = patch_for(dataset, name)
    try:
        return entry.decoder.decode(_load(url), entry.variable)
    except ValueError as e:
        raise ValueError(f"{dataset}, file {url}: {e}") from e


def patched_reader(entry: PatchedParameter) -> FileLoaderCallable:
    def read(url: Optional[str], variable: str, **kwargs) -> Optional[SpeasyVariable]:
        if url is None:
            return None
        return _read_patched(url, entry.dataset, entry.name, **kwargs)

    return read
