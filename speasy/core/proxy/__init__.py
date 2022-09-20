from speasy.config import proxy as proxy_cfg
from functools import wraps
from .. import http
from ...products.variable import from_dictionary as var_from_dict
from ..inventory.indexes import from_dict as inventory_from_dict
import pickle
import logging
from packaging.version import Version

log = logging.getLogger(__name__)
PROXY_ALLOWED_KWARGS = ['disable_proxy']
MINIMUM_REQUIRED_PROXY_VERSION = Version("0.6.0")
_CURRENT_PROXY_SERVER_VERSION = None


def query_proxy_version():
    global _CURRENT_PROXY_SERVER_VERSION
    if _CURRENT_PROXY_SERVER_VERSION is None:
        url = proxy_cfg.url()
        if url != "":
            resp = http.get(f"{url}/get_version?")
            if resp.status_code == 200:
                _CURRENT_PROXY_SERVER_VERSION = Version(resp.text.strip())
                return _CURRENT_PROXY_SERVER_VERSION
    return _CURRENT_PROXY_SERVER_VERSION


try:
    import zstd

    zstd_compression = 'true'


    def decompress(data):
        return zstd.decompress(data)

except ImportError:
    zstd_compression = 'false'


    def decompress(data):
        return data


class GetProduct:
    def __init__(self):
        pass

    @staticmethod
    def get(path: str, start_time: str, stop_time: str, **kwargs):
        url = proxy_cfg.url()
        kwargs['path'] = path
        kwargs['start_time'] = start_time
        kwargs['stop_time'] = stop_time
        kwargs['format'] = 'python_dict'
        kwargs['zstd_compression'] = zstd_compression
        resp = http.get(f"{url}/get_data?", params=kwargs)
        log.debug(f"Asking data from proxy {resp.url}, {resp.request.headers}")
        if resp.status_code == 200:
            var = var_from_dict(pickle.loads(decompress(resp.content)))
            return var
        return None


class GetInventory:
    @staticmethod
    def get(provider: str, **kwargs):
        url = proxy_cfg.url()
        kwargs['provider'] = provider
        kwargs['format'] = 'python_dict'
        kwargs['zstd_compression'] = zstd_compression
        resp = http.get(f"{url}/get_inventory?", params=kwargs)
        log.debug(f"Asking {provider} inventory from proxy {resp.url}, {resp.request.headers}")
        if resp.status_code == 200:
            var = inventory_from_dict(pickle.loads(decompress(resp.content)))
            return var
        return None


class Proxyfiable(object):
    def __init__(self, request, arg_builder):
        self.request = request
        self.arg_builder = arg_builder

    def __call__(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            disable_proxy = kwargs.pop("disable_proxy", False)
            if proxy_cfg.enabled() and not disable_proxy:
                try:
                    proxy_version = query_proxy_version()
                    if proxy_version is not None and proxy_version >= MINIMUM_REQUIRED_PROXY_VERSION:
                        return self.request.get(**self.arg_builder(**kwargs))
                    else:
                        log.warning(
                            f"You are using an incompatible proxy server {proxy_cfg.url()} which is {proxy_version} while minimun required version is {MINIMUM_REQUIRED_PROXY_VERSION}")
                except: # lgtm [py/catch-base-exception]
                    log.error(f"Can't get data from proxy server {proxy_cfg.url()}") 
            return func(*args, **kwargs)

        return wrapped
