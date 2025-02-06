from typing import Dict, Tuple, Callable
from urllib.parse import urlparse, urlencode
from functools import wraps

from speasy.config import core as core_config

_REWRITE_RULES_ = core_config.http_rewrite_rules.get()


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


def host_and_port(url: str) -> Tuple[str, int]:
    """Returns the host and port of an url

    Parameters
    ----------
    url : str
        url with or without scheme

    Returns
    -------
    Tuple[str, str]
        host and port of the url, defaults to 80 if no port or scheme is provided
    """
    parsed = urlparse(url)
    if parsed.port is not None:
        return parsed.hostname, parsed.port
    elif parsed.scheme == 'http':
        return parsed.hostname, 80
    elif parsed.scheme == 'https':
        return parsed.hostname, 443

    return parsed.hostname, 80


def apply_rewrite_rules(url: str) -> str:
    for base_url in _REWRITE_RULES_:
        if url.startswith(base_url):
            return _REWRITE_RULES_[base_url] + url[len(base_url):]
    return url


class ApplyRewriteRules:

    def __init__(self, is_method: bool = False):
        self.is_method = is_method

    def __call__(self, f: Callable):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if self.is_method:
                wrapped_self = args[0]
                args = args[1:]
            if 'url' in kwargs:
                url = kwargs.pop('url')
            elif len(args):
                url = args[0]
                args = args[1:]
            else:
                url = None
            if url is not None:
                url = apply_rewrite_rules(url)
            if self.is_method:
                return f(wrapped_self, url, *args, **kwargs)
            return f(url, *args, **kwargs)

        return wrapper


def extract_path(url: str) -> str:
    return urlparse(url).path
