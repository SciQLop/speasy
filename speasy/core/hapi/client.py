from enum import Enum
from typing import Dict, Optional

from speasy.core import http

from .exceptions import HapiError, HapiRequestError, HapiServerError, HapiNoData


class HapiEndpoint(Enum):
    CAPABILITIES = "capabilities"
    CATALOG      = "catalog"
    ABOUT        = "about"
    INFO         = "info"
    DATA         = "data"


class HapiClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')

    def _build_url(self, endpoint: HapiEndpoint = None) -> str:
        hapi_url = f"{self.server_url}/hapi"
        if endpoint is None:
            return hapi_url
        if not isinstance(endpoint, HapiEndpoint):
            raise TypeError(f"endpoint must be a HapiEndpoint, got {type(endpoint)}")
        return f"{hapi_url}/{endpoint.value}"

    def _jsondict_from_simple_url(self, endpoint: HapiEndpoint) -> Dict:
        url = self._build_url(endpoint)
        with http.urlopen(url, headers={"Accept": "application/json"}) as response:
            data = response.json()
        return data

    def _check_status(self, response_json: Dict) -> None:
        """Lit response_json['status'], lève la bonne HapiError si besoin."""
        ...

    def get_hapi(self) -> Dict:
        url = self._build_url()
        print(url)
        with http.urlopen(url) as response:
            html_page = response.text
        return html_page

    def get_capabilities(self) -> Dict:
        return self._jsondict_from_simple_url(HapiEndpoint.CAPABILITIES)

    def get_catalog(self) -> Dict:
        ...

    def get_info(self, dataset: str) -> Dict: ...

    def get_data(self, dataset: str, start: str, stop: str,
                 parameters: Optional[str] = None) -> bytes: ...

    def get_about(self) -> Dict:
        return self._jsondict_from_simple_url(HapiEndpoint.ABOUT)
