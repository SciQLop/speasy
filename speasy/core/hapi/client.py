from enum import Enum
from json import JSONDecodeError
from typing import Dict, List, Optional
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
        self._dataset_param_name = self._init_dataset_param_name()

    def _init_dataset_param_name(self) -> str:
        """ Starting from HAPI-3.0, 'id' parameter becomes 'dataset'
            set by major version number
        """
        version = self.get_capabilities().get("HAPI")

        if not version:
            raise RuntimeError("HAPI version not provided by server")

        major = int(version.split('.')[0])

        if major == 2:
            return "id"
        elif  major == 3:
            return "dataset"

        raise RuntimeError(f"Unsupported HAPI version: {version}")

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
        with http.urlopen(url) as response:
            html_page = response.text
        return html_page

    def get_capabilities(self) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.CAPABILITIES)

    def get_catalog(self) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.CATALOG)

    def get_about(self) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.ABOUT)

    def get_info(self, dataset: str, parameters: Optional[List[str]] = None) -> Dict:
        base_params = {}

        if parameters:
            if isinstance(parameters, str):
                parameters = [parameters]
            base_params["parameters"] = ",".join(parameters)

        return self._endpoint_to_json(
            HapiEndpoint.INFO, {self._dataset_param_name: dataset, **base_params}
        )

    def get_data(self, dataset: str, start: str, stop: str,
                 parameters: Optional[str] = None) -> bytes: ...
