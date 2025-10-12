import io
import logging
import os
import re
from datetime import timedelta, datetime
from typing import List, Optional, Union
from speasy.core.cache import CacheCall
from speasy.core.cache import get_item, add_item, CacheItem, request_locker
from . import http
from .url_utils import is_local_file, extract_path

log = logging.getLogger(__name__)
_HREF_REGEX = re.compile('''href=['"]([A-Za-z0-9-_./]+)['"]>''')


class AnyFile(io.IOBase):
    def __init__(self, url, file_impl: io.IOBase, status=200):
        self._url = url
        self._file_impl = file_impl
        self._status = status

    @property
    def url(self):
        return self._url

    def read(self, *args, **kwargs):
        return self._file_impl.read(*args, **kwargs)

    def readline(self, *args, **kwargs):
        return self._file_impl.readline(*args, **kwargs)

    def seek(self, *args, **kwargs):
        return self._file_impl.seek(*args, **kwargs)

    def close(self):
        return self._file_impl.close()

    @property
    def ok(self):
        return (self._status in (200, 304)) and self._file_impl.readable()

    @property
    def status_code(self):
        return self._status

    def __del__(self):
        if not self._file_impl.closed:
            self.close()

    def __getattr__(self, item):
        return getattr(self._file_impl, item)


def _remote_open(url, timeout: int = http.DEFAULT_TIMEOUT, headers: dict = None, mode='rb'):
    resp = http.urlopen(url=url, headers=headers, timeout=timeout)
    if resp.status != 200:
        raise IOError(f"Could not open remote file {url}: HTTP {resp.status}")
    if 'b' in mode:
        return AnyFile(url, io.BytesIO(resp.bytes))
    else:
        return AnyFile(url, io.StringIO(resp.text))


def _make_file_from_cache_entry(entry: CacheItem, url: str, mode: str) -> AnyFile:
    if 'b' in mode:
        return AnyFile(url, io.BytesIO(entry.data))
    else:
        return AnyFile(url, io.StringIO(entry.data))


def _is_outdated(entry: CacheItem, url: str) -> bool:
    try:
        last_modified = http.head(url).headers.get('last-modified', str(datetime.now()))
        return last_modified != entry.version
    except Exception as e:
        log.warning(f"Could not check if remote file {url} is outdated: {e}")
        return False

def _cached_get_remote_file(url, timeout: int = http.DEFAULT_TIMEOUT, headers: dict = None, mode='rb',
                            prefer_cache=False) -> AnyFile:

    with request_locker(url):
        entry = get_item(url)
        if not isinstance(entry, CacheItem) or (not prefer_cache and _is_outdated(entry, url)):
            resp = http.urlopen(url=url, headers=headers, timeout=timeout)
            last_modified = resp.headers.get('last-modified', str(datetime.now()))
            if 'b' in mode:
                entry = CacheItem(data=resp.bytes, version=last_modified)
            else:
                entry = CacheItem(data=resp.text, version=last_modified)
            add_item(key=url, item=entry)
        return _make_file_from_cache_entry(entry, url, mode)


def any_loc_open(url, timeout: int = http.DEFAULT_TIMEOUT, headers: Optional[dict] = None, mode='rb',
                 cache_remote_files=False, prefer_cache=False) -> AnyFile:
    """Opens a file at the specified URL, whether local or remote.

    Parameters
    ----------
    url : str
        The file URL, formatted as either a local path or a standard URL (https://en.wikipedia.org/wiki/URL).
    timeout : int
        The timeout duration in seconds for remote files (default: 60 seconds).
    headers : Optional[dict]
        Optional HTTP headers to include when requesting remote files.
    mode : str
        The file open mode. Only 'r' or 'rb' are supported.
    cache_remote_files : bool
        Determines whether remote files are stored in the Speasy cache for future requests. Files are only downloaded
        if they have changed (based on the 'last-modified' header field).
    prefer_cache : bool
        If True, the cache is used even if the remote file has changed. This can be useful to avoid repeated downloads of
        frequently changing files or when working offline.

    Returns
    -------
    AnyFile
        The opened file object.

    """
    if is_local_file(url):
        return AnyFile(url, open(url.replace('file://', ''), mode=mode))
    else:
        if cache_remote_files:
            return _cached_get_remote_file(url, timeout=timeout, headers=headers, mode=mode, prefer_cache=prefer_cache)
        else:
            return _remote_open(url, timeout=timeout, headers=headers, mode=mode)


def _list_local_files(path: str) -> List[str]:
    return os.listdir(path)


def _make_remote_files_relative(ref_path: str, path: str):
    if path.startswith('/') and len(ref_path) > 1:
        return path.removeprefix(ref_path)
    return path


@CacheCall(cache_retention=timedelta(hours=12), is_pure=True)
def _list_remote_files(url: str) -> List[str]:
    if not url.endswith('/'):
        url += '/'
    response = http.get(url)
    if response.ok:
        path = extract_path(url)
        return list(map(lambda f: _make_remote_files_relative(path, f), _HREF_REGEX.findall(response.text)))
    return []


def list_files(url: str, file_regex: Union[re.Pattern, str], disable_cache=False, force_refresh=False) -> List[str]:
    """Lists files that match the specified regex pattern either from a web page generated by Apache mod_dir or
    equivalent, or from a local directory.

    Parameters
    ----------
    url : str
        The URL or local path to scan.
    file_regex : re.Pattern or str
        The regular expression pattern used to filter files.
    disable_cache : bool
        Determines whether the cache is disabled for remote file listings.
    force_refresh : bool
        Forces a refresh of the cache for remote file listings.

    Returns
    -------
    List[str]
        A list of files that match the specified regex pattern, either from a remote source or a local directory.
    """
    if type(file_regex) is str:
        file_regex = re.compile(file_regex)
    if is_local_file(url):
        files = _list_local_files(url.replace('file://', ''))
    else:
        files = _list_remote_files(url, disable_cache=disable_cache, force_refresh=force_refresh)
    return list(filter(file_regex.match, files))
