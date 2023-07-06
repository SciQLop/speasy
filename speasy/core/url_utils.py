from typing import Dict
from urllib.parse import urlparse, urlencode


def quote(*args, **kwargs):
    from urllib.parse import quote as _quote
    return _quote(*args, **kwargs)


def ensure_url_scheme(url: str) -> str:
    """Adds file:// to url for local files

    Parameters
    ----------
    url : str
        url with or without scheme
    Returns
    -------
    str
        url with 'file:' scheme added when none was provided else input url
    """
    parsed = urlparse(url)
    if parsed.scheme != 'file' and parsed.netloc == '':
        return f"file://{url}"
    return url


def is_local_file(url: str):
    """Returns true if url correspond to a local path.

    Parameters
    ----------
    url : str
        file url formatted as local path or standard URL format (https://en.wikipedia.org/wiki/URL)

    Returns
    -------
    bool
        True if matches any local path/URL


    Examples
    --------

    >>> from speasy.core.url_utils import is_local_file

    >>> is_local_file("/some/path")
    True

    >>> is_local_file("C:/some/path")
    True

    >>> is_local_file("file:///some/path")
    True

    >>> is_local_file("http://some/path")
    False

    """
    split_url = urlparse(url)
    return split_url.scheme in ('', 'file') or split_url.netloc == ''


def build_url(base: str, parameters: Dict) -> str:
    return base + '?' + urlencode(parameters)
