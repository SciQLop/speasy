from urllib.parse import urlparse, urlunparse, urlencode
from typing import Dict


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
    if parsed.scheme == '':
        return urlunparse(parsed._replace(scheme='file'))
    return url


def is_local_file(url):
    split_url = urlparse(url)
    return split_url.scheme in ('', 'file')


def build_url(base: str, parameters: Dict) -> str:
    return base + '?' + urlencode(parameters)
