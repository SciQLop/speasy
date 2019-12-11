from ..config import proxy_enabled, proxy_url
from functools import wraps
import requests
import pickle


class GetProduct:
    def __init__(self):
        pass

    @staticmethod
    def get(path:str, start_time:str, stop_time:str):
        url = proxy_url.get()
        resp=requests.get(f"{url}/get_data?path={path}&start_time={start_time}&stop_time={stop_time}")
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
