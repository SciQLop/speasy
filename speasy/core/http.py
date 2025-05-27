import json
import logging
import platform
import re
import time
from functools import partial, cache
from typing import Optional, Dict

import urllib3.response
from urllib3 import PoolManager
from urllib3.util.retry import Retry
import netrc

from speasy import __version__
from speasy.config import core as core_config
from .url_utils import host_and_port, ApplyRewriteRules

log = logging.getLogger(__name__)

USER_AGENT = f'Speasy/{__version__} {platform.uname()} (SciQLop project)'

DEFAULT_TIMEOUT = 60  # seconds

DEFAULT_DELAY = 5  # seconds

DEFAULT_RETRY_COUNT = 5

STATUS_FORCE_LIST = [500, 502, 504, 413, 429, 503]

RETRY_AFTER_LIST = [429, 503]  # Note: Specific treatment for 429 & 503 error codes (see below)

_HREF_REGEX = re.compile(' href="([A-Za-z0-9.-_]+)">')

pool = PoolManager(num_pools=core_config.urlib_num_pools.get(), maxsize=core_config.urlib_pool_size.get())


class Response:
    def __init__(self, response: urllib3.response.BaseHTTPResponse):
        self._response = response

    @property
    def status_code(self):
        return self._response.status

    @property
    def text(self):
        return self._response.data.decode()

    @property
    def headers(self):
        return self._response.headers

    def json(self):
        return json.loads(self._response.data)

    @property
    def bytes(self):
        return self._response.data

    @property
    def url(self):
        return self._response.geturl()

    @property
    def ok(self):
        return self.status_code in (200, 304)

    def __getattr__(self, item):
        return getattr(self._response, item)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

@cache
def _auth(hostname:str)-> Dict[str, str]:
    """
    Authenticates a user for a specified hostname by retrieving credentials from
    the user's `.netrc` file if it exists. Utilizes caching for performance.

    Parameters:
        hostname: The hostname for which credentials need to be fetched.

    Returns:
        Dict[str, str]: A dictionary containing headers for basic authentication
        if the credentials are available in the `.netrc` file. If no credentials
        are found or the file is not present, an empty dictionary is returned.
    """
    try:
        netrc_file = netrc.netrc()
        auth = netrc_file.authenticators(hostname)
        if auth:
            username, _, password = auth
            return urllib3.make_headers(basic_auth=f'{username}:{password}')
    except FileNotFoundError:
        pass
    return {}

@ApplyRewriteRules()
def auth_header(url: str) -> Dict[str, str]:
    """
    Generate authentication headers for a given URL.

    This function processes a URL to extract its hostname and generates
    authentication headers based on the hostname. It uses auxiliary functions
    to determine the hostname and retrieve the authentication details.
    The authentication credentials are read from the user's .netrc file.

    Args:
        url (str): The URL for which to generate authentication headers.

    Returns:
        Dict[str, str]: A dictionary containing the authentication headers
        corresponding to the provided URL.

    Raises:
        None
    """
    hostname,_ = host_and_port(url)
    return _auth(hostname)


def _build_headers(url: str, headers: Dict = None) -> Dict[str, str]:
    """
    Construct HTTP headers for a given URL, including a default User-Agent and
    authorization headers.

    Parameters:
    url : str
        The URL for which the headers are being constructed.
    headers : Dict, optional
        Existing headers to include in the request. Defaults to an empty dictionary
        if not provided.

    Returns:
    Dict[str, str]
        A dictionary containing the constructed HTTP headers.
    """
    headers = headers or {}
    headers['User-Agent'] = USER_AGENT
    headers.update(auth_header(url))
    return headers


class _HttpVerb:
    def __init__(self, verb):
        # cf. https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/
        retry_strategy = Retry(
            total=DEFAULT_RETRY_COUNT,
            backoff_factor=1,
            status_forcelist=STATUS_FORCE_LIST,
            allowed_methods=[verb],
            respect_retry_after_header=True
        )
        # self._adapter = TimeoutHTTPAdapter(max_retries=retry_strategy, timeout=DEFAULT_TIMEOUT)
        # self._http = requests.Session()
        # self._http.mount("https://", self._adapter)
        # self._http.mount("http://", self._adapter)
        self._verb = partial(pool.request, method=verb, retries=retry_strategy)

    @ApplyRewriteRules(is_method=True)
    def __call__(self, url, headers: dict = None, params: dict = None, timeout: int = DEFAULT_TIMEOUT):
        # self._adapter.timeout = timeout
        return Response(
            self._verb(url=url, headers=_build_headers(url=url, headers=headers), fields=params, timeout=timeout))


get = _HttpVerb("GET")
head = _HttpVerb("HEAD")


@ApplyRewriteRules()
def urlopen(url, timeout: int = DEFAULT_TIMEOUT, headers: dict = None):
    return Response(
        pool.urlopen(method="GET", url=url, headers=_build_headers(url=url, headers=headers), timeout=timeout))


@ApplyRewriteRules()
def is_server_up(url: Optional[str] = None, host: Optional[str] = None, port: Optional[int] = None, timeout: int = 5,
                 retries=5) -> bool:
    """Checks if a server is up and running. If url is provided, host and port are ignored.

    Parameters
    ----------
    url : Optional[str]
        url to check (scheme://host[:port]), if provided host and port are ignored
    host : Optional[str]
        host to check, if provided port must be provided as well
    port : Optional[int]
        port to check, if provided host must be provided as well
    timeout : int
        timeout in seconds

    Returns
    -------
    bool
        True if server is up and running, False otherwise

    Raises
    ------
    ValueError
        If neither url nor host and port are provided
    """
    if url is not None:
        host, port = host_and_port(url)
    elif host is None or port is None:
        raise ValueError("Either url or host and port must be provided")
    import socket
    try:
        for _ in range(retries):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            if result == 0:
                return True
            log.debug(f"Server {host}:{port} not up yet, retrying in 1 second")
            time.sleep(1.)
        return False
    except Exception as e:
        log.error(f"Error while checking server status: {e}")
        return False
