from speasy import __version__
import platform
import requests
from requests.utils import quote as _quote
from time import sleep
import logging

log = logging.getLogger(__name__)

USER_AGENT = f'Speasy/{__version__} {platform.uname()} (SciQLop project)'

def quote(*args, **kwargs):
    return _quote(*args, **kwargs)

def get(url, headers: dict = None, params: dict = None):
    headers = {} if headers is None else headers
    headers['User-Agent'] = USER_AGENT
    resp = requests.get(url, headers=headers, params=params)
    while resp.status_code in [429, 503]:
        try:
            delay = float(resp.headers['Retry-After'])
        except ValueError:
            delay = 5
        log.debug(f"Got {resp.status_code} response, will sleep for {delay} seconds")
        sleep(delay)
        resp = requests.get(url, headers=headers, params=params)
    return resp
