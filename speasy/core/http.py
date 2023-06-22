import json
import logging
import platform
import re
from functools import partial

import urllib3.response
from urllib3 import PoolManager
from urllib3.util.retry import Retry

from speasy import __version__

log = logging.getLogger(__name__)

USER_AGENT = f'Speasy/{__version__} {platform.uname()} (SciQLop project)'

DEFAULT_TIMEOUT = 60  # seconds

DEFAULT_DELAY = 5  # seconds

DEFAULT_RETRY_COUNT = 5

STATUS_FORCE_LIST = [500, 502, 504, 413, 429, 503]

RETRY_AFTER_LIST = [429, 503]  # Note: Specific treatment for 429 & 503 error codes (see below)

_HREF_REGEX = re.compile(' href="([A-Za-z0-9.-_]+)">')

pool = PoolManager()


class Response:
    def __init__(self, response: urllib3.response.HTTPResponse):
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

    def __call__(self, url, headers: dict = None, params: dict = None, timeout: int = DEFAULT_TIMEOUT):
        # self._adapter.timeout = timeout
        headers = headers or {}
        headers['User-Agent'] = USER_AGENT
        return Response(self._verb(url=url, headers=headers, fields=params, timeout=timeout))


get = _HttpVerb("GET")
head = _HttpVerb("HEAD")


def urlopen(url, timeout: int = DEFAULT_TIMEOUT, headers: dict = None):
    headers = {} if headers is None else headers
    headers['User-Agent'] = USER_AGENT
    return Response(pool.urlopen(method="GET", url=url, headers=headers, timeout=timeout))
