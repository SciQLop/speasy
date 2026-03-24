from enum import Enum
from json import JSONDecodeError
from typing import Dict, Optional
from urllib.parse import urlencode

from speasy.core import http

from .exceptions import HapiRequestError, HapiServerError, HapiNoData


class HapiEndpoint(Enum):
    CAPABILITIES = "capabilities"
    CATALOG      = "catalog"
    ABOUT        = "about"
    INFO         = "info"
    DATA         = "data"


class HapiClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')

    def _build_url(self, endpoint: Optional[HapiEndpoint] = None, query_parameters: Optional[Dict] = None) -> str:
        hapi_url = f"{self.server_url}/hapi"
        if endpoint is None:
            return hapi_url
        if not isinstance(endpoint, HapiEndpoint):
            raise TypeError(f"endpoint must be a HapiEndpoint, got {type(endpoint)}")
        return f"{hapi_url}/{endpoint.value}"

    def _build_url(
        self,
        endpoint: Optional[HapiEndpoint] = None,
        query_parameters: Optional[Dict] = None
    ) -> str:
        base = f"{self.server_url}/hapi"

        if endpoint is None:
            url = base
        else:
            if not isinstance(endpoint, HapiEndpoint):
                raise TypeError(f"endpoint must be a HapiEndpoint, got {type(endpoint)}")
            url = f"{base}/{endpoint.value}"

        if query_parameters:
            query_string = urlencode(query_parameters)
            url = f"{url}?{query_string}"

        return url

    def _endpoint_to_json(
            self,
            endpoint: Optional[HapiEndpoint] = None,
            query_parameters: Optional[Dict] = None
    ) -> Dict:
        url = self._build_url(endpoint, query_parameters)
        r = http.get(url)
        try:
            data = r.json()
            self._check_hapi_status(data)
            return data
        except JSONDecodeError:
            self._check_http_status(r.status_code, r.text)

    def _check_hapi_status(self, data: Dict) -> None:
        code = data["status"]["code"]
        message = data["status"]["message"]
        if code == 1201:
            raise HapiNoData()
        elif 1400 <= code < 1500:
            raise HapiRequestError(code, message)
        elif code >= 1500:
            raise HapiServerError(code, message)

    def _check_http_status(self, status_code: int, text: str) -> None:
        if 400 <= status_code < 500:
            raise HapiRequestError(status_code, text)
        elif status_code >= 500:
            raise HapiServerError(status_code, text)

    def get_hapi(self) -> Dict:
        url = self._build_url()
        print(url)
        with http.urlopen(url) as response:
            html_page = response.text
        return html_page

    def get_capabilities(self) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.CAPABILITIES)

    def get_catalog(self) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.CATALOG)

    def get_about(self) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.ABOUT)

    def get_info(self, dataset: str, ) -> Dict:
        # Starting from HAPI-3.0 'id' parameter becomes 'dataset' 
        try:
            r_json = self._endpoint_to_json(HapiEndpoint.INFO, {'id': dataset})
        except HapiRequestError:
            r_json = self._endpoint_to_json(HapiEndpoint.INFO, {'dataset': dataset})
        return r_json

    def get_data(self, dataset: str, start: str, stop: str,
                 parameters: Optional[str] = None) -> bytes: ...