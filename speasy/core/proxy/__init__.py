import logging
import pickle
import warnings
from datetime import datetime, timedelta
from functools import wraps

from dateutil import parser
from packaging.version import Version

from speasy.config import inventories as inventories_cfg
from speasy.config import proxy as proxy_cfg
from .. import http
from ..index import index
from ..inventory.indexes import from_dict as inventory_from_dict
from ... import SpeasyIndex
from ...products.variable import from_dictionary as var_from_dict
from ..cache import CacheCall

log = logging.getLogger(__name__)
PROXY_ALLOWED_KWARGS = ['disable_proxy']
MINIMUM_REQUIRED_PROXY_VERSION = Version("0.8.0")
_CURRENT_PROXY_SERVER_VERSION = None

if proxy_cfg.url() == "" or proxy_cfg.enabled() == False:
    warnings.warn("""Proxy server is disabled you might want to use it both to improve Speasy performances and to reduce pressure on remote servers
use the following python snippet to configure proxy server:
===========================================================================
import speasy as spz
spz.config.proxy.url.set("http://sciqlop.lpp.polytechnique.fr/cache")
spz.config.proxy.enabled.set(True)
===========================================================================
            """, stacklevel=0)


def query_proxy_version():
    global _CURRENT_PROXY_SERVER_VERSION
    if _CURRENT_PROXY_SERVER_VERSION is None:
        url = proxy_cfg.url()
        if url != "":
            resp = http.get(f"{url}/get_version")
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


@CacheCall(cache_retention=timedelta(minutes=10), is_pure=True)
def is_proxy_up() -> bool:
    if http.is_server_up(proxy_cfg.url()):
        try:
            r = http.get(f"{proxy_cfg.url()}/get_inventory", params={"provider": "ssc"}, timeout=1)
            return r.status_code == 200
        except:  # lgtm [py/catch-base-exception]
            pass
    return False


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
        resp = http.get(f"{url}/get_data", params=kwargs)
        log.debug(f"Asking data from proxy {resp.url}, {resp.headers}")
        if resp.status_code == 200:
            var = var_from_dict(pickle.loads(decompress(resp.bytes)))
            return var
        return None


class GetInventory:
    @staticmethod
    def get(provider: str, **kwargs):
        saved_inventory: SpeasyIndex = index.get("proxy_inventories", provider, None)
        saved_inventory_dt: datetime = index.get("proxy_inventories_save_date", provider, datetime.utcfromtimestamp(0))
        if saved_inventory_dt + timedelta(days=inventories_cfg.cache_retention_days.get()) > datetime.utcnow():
            return saved_inventory

        url = proxy_cfg.url()
        kwargs['provider'] = provider
        kwargs['format'] = 'python_dict'
        kwargs['zstd_compression'] = zstd_compression
        headers = {}
        if saved_inventory is not None:
            headers["If-Modified-Since"] = parser.parse(saved_inventory.build_date).ctime()
        resp = http.get(f"{url}/get_inventory", params=kwargs, headers=headers)
        log.debug(f"Asking {provider} inventory from proxy {resp.url}, {resp.headers}")
        if resp.status_code == 200:
            inventory = inventory_from_dict(pickle.loads(decompress(resp.bytes)))
            index.set("proxy_inventories", provider, inventory)
            index.set("proxy_inventories_save_date", provider, datetime.utcnow())
            return inventory
        if resp.status_code == 304:
            return saved_inventory
        return None


class Proxyfiable(object):
    def __init__(self, request, arg_builder):
        self.request = request
        self.arg_builder = arg_builder

    def __call__(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            disable_proxy = kwargs.pop("disable_proxy", False)
            if proxy_cfg.enabled() and not disable_proxy and is_proxy_up():
                try:
                    proxy_version = query_proxy_version()
                    if proxy_version is not None and proxy_version >= MINIMUM_REQUIRED_PROXY_VERSION:
                        return self.request.get(**self.arg_builder(**kwargs))
                    else:
                        log.warning(
                            f"You are using an incompatible proxy server {proxy_cfg.url()} which is {proxy_version} while minimun required version is {MINIMUM_REQUIRED_PROXY_VERSION}")
                except:  # lgtm [py/catch-base-exception]
                    log.error(f"Can't get data from proxy server {proxy_cfg.url()}")
            return func(*args, **kwargs)

        return wrapped
