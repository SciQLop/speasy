from enum import Enum
from typing import Dict, Optional

from speasy.core import http

from .exceptions import HapiError, HapiRequestError, HapiServerError, HapiNoData


class HapiEndpoint(Enum):
    CAPABILITIES = "capabilities"
    CATALOG      = "catalog"
    INFO         = "info"
    DATA         = "data"
    ABOUT        = "about"


class HapiClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')

    def _build_url(self, endpoint: HapiEndpoint) -> str:
        return f"{self.server_url}/hapi/{endpoint.value}"

    def _get_simple_url(self, endpoint: HapiEndpoint) -> Dict:
        url = self._build_url(endpoint)
        with http.urlopen(url, headers={"Accept": "application/json"}) as response:
            data = response.json()
        return data


    def _check_status(self, response_json: Dict) -> None:
        """Lit response_json['status'], lève la bonne HapiError si besoin."""
        ...

    def get_capabilities(self) -> Dict:
        return self._get_simple_url(HapiEndpoint.CAPABILITIES)

    def get_catalog(self) -> Dict:
        ...

    def get_info(self, dataset: str) -> Dict: ...

    def get_data(self, dataset: str, start: str, stop: str,
                 parameters: Optional[str] = None) -> bytes: ...

    def get_about(self) -> Dict:
        return self._get_simple_url(HapiEndpoint.ABOUT)

