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

STATUS_FORCE_LIST = [500, 502, 503, 504]  # Note: Specific treatment for 429 error code (see below)


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


def quote(*args, **kwargs):
    return _quote(*args, **kwargs)


def get(url, headers: dict = None, params: dict = None, timeout: int = DEFAULT_TIMEOUT):
    headers = {} if headers is None else headers
    headers['User-Agent'] = USER_AGENT
    # cf. https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/
    retry_strategy = Retry(
        total=DEFAULT_RETRY_COUNT,
        backoff_factor=1,
        status_forcelist=STATUS_FORCE_LIST,
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = TimeoutHTTPAdapter(max_retries=retry_strategy, timeout=timeout)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    resp = http.get(url, headers=headers, params=params)
    while resp.status_code == 429:  # Honor "Retry-After"
        try:
            delay = float(resp.headers['Retry-After'])
        except ValueError:
            delay = DEFAULT_DELAY
        log.debug(f"Got {resp.status_code} response, will sleep for {delay} seconds")
        sleep(delay)
        resp = http.get(url, headers=headers, params=params)
    return resp


def urlopen_with_retry(url, timeout: int = DEFAULT_TIMEOUT, headers: dict = None):
    headers = {} if headers is None else headers
    headers['User-Agent'] = USER_AGENT
    req = Request(url, headers=headers)
    retrycount = 0
    s = None
    delay = DEFAULT_DELAY
    while s is None:
        try:
            resp = urlopen(req, timeout=timeout)
            return resp
        except HTTPError as e:
            if isinstance(e.reason, socket.timeout):
                log.debug(f"Timeout exception during urlopen request, will sleep for {delay} seconds")
            elif e.code in STATUS_FORCE_LIST:
                log.debug(f"HTTP Error Got {e.code} response, will sleep for {delay} seconds")
            elif e.code == 429:  # Honor "Retry-After"
                try:
                    delay = float(resp.headers['Retry-After'])
                except ValueError:
                    pass
                log.debug(f"Got {e.code} response, will sleep for {delay} seconds")
                sleep(delay)
                return urlopen_with_retry(url, timeout=timeout, headers=headers)
            else:
                raise e
            retrycount += 1
            if retrycount > DEFAULT_RETRY_COUNT:
                raise e
            sleep(DEFAULT_DELAY)
        except URLError as e:
            log.debug(f"Got {e.reason} error, will sleep for {delay} seconds")
            retrycount += 1
            if retrycount > DEFAULT_RETRY_COUNT:
                raise e
            sleep(DEFAULT_DELAY)
