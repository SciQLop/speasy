from ..config import proxy_enabled, proxy_url
from functools import wraps
import requests
import pickle
import logging

log = logging.getLogger(__name__)


class GetProduct:
    def __init__(self):
        pass

    @staticmethod
    def get(path: str, start_time: str, stop_time: str, **kwargs):
        url = proxy_url.get()
        kwargs['path']=path
        kwargs['start_time'] = start_time
        kwargs['stop_time'] = stop_time
        resp = requests.get(f"{url}/get_data?", params=kwargs)
        log.debug(f"Asking data from proxy {resp.url}, {resp.request.headers}")
        if resp.status_code == 200:
            var = pickle.loads(resp.content)
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
            if proxy_enabled.get().lower() == "true" and not disable_proxy:
                return self.request.get(**self.arg_builder(**kwargs))
            else:
                return func(*args, **kwargs)

        return wrapped
