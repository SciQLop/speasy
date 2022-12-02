from speasy import __version__
import platform
import requests
import socket
from requests.utils import quote as _quote
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.request import Request, urlopen, HTTPError, URLError
from time import sleep
import logging

log = logging.getLogger(__name__)

USER_AGENT = f'Speasy/{__version__} {platform.uname()} (SciQLop project)'

DEFAULT_TIMEOUT = 60  # seconds

DEFAULT_DELAY = 5  # seconds

DEFAULT_RETRY_COUNT = 5

STATUS_FORCE_LIST = [500, 502, 504]

RETRY_AFTER_LIST = [429, 503]  # Note: Specific treatment for 429 & 503 error codes (see below)


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, timeout=DEFAULT_TIMEOUT, **kwargs):
        self.timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        kwargs.pop('timeout', None)
        return super().send(request, timeout=self.timeout, **kwargs)


def quote(*args, **kwargs):
    return _quote(*args, **kwargs)


def apply_delay(headers: dict = None):
    delay = DEFAULT_DELAY
    try:
        if headers and ('Retry-After' in headers):
            delay = float(headers['Retry-After'])
    except ValueError:
        pass
    log.debug(f"Will sleep for {delay} seconds")
    sleep(delay)


def get(url, headers: dict = None, params: dict = None, timeout: int = DEFAULT_TIMEOUT, head_only: bool = False):
    headers = {} if headers is None else headers
    headers['User-Agent'] = USER_AGENT
    # cf. https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/
    retry_strategy = Retry(
        total=DEFAULT_RETRY_COUNT,
        backoff_factor=1,
        status_forcelist=STATUS_FORCE_LIST,
        allowed_methods=["HEAD", "GET"]
    )
    adapter = TimeoutHTTPAdapter(max_retries=retry_strategy, timeout=timeout)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    while True:
        if head_only:
            resp = http.head(url, headers=headers, params=params)
        else:
            resp = http.get(url, headers=headers, params=params)
        if resp.status_code in RETRY_AFTER_LIST:  # Honor "Retry-After"
            log.debug(f"Got {resp.status_code} response")
            apply_delay(resp.headers)
        else:
            break
    return resp


def urlopen_with_retry(url, timeout: int = DEFAULT_TIMEOUT, headers: dict = None):
    headers = {} if headers is None else headers
    headers['User-Agent'] = USER_AGENT
    req = Request(url, headers=headers)
    retrycount = 0
    while True:
        try:
            resp = urlopen(req, timeout=timeout)
            return resp
        except HTTPError as e:
            if isinstance(e.reason, socket.timeout):
                log.debug("Timeout exception during urlopen request")
            elif e.code in STATUS_FORCE_LIST:
                log.debug(f"HTTP Error Got {e.code} response")
            elif e.code in RETRY_AFTER_LIST:  # Honor "Retry-After"
                log.debug(f"Got {e.code} response")
                apply_delay(resp.headers)
                return urlopen_with_retry(url, timeout=timeout, headers=headers)
            else:
                raise e
            retrycount += 1
            if retrycount > DEFAULT_RETRY_COUNT:
                raise e
            apply_delay()
        except URLError as e:
            log.debug(f"Got {e.reason} error")
            retrycount += 1
            if retrycount > DEFAULT_RETRY_COUNT:
                raise e
            apply_delay()
