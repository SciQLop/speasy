from .. import __version__
import platform
import requests

USER_AGENT = f'Speasy/{__version__} {platform.uname()} (SciQLop project)'


def get(url, headers={}):
    headers['User-Agent'] = USER_AGENT
    return requests.get(url, headers=headers)
