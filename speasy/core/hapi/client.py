from enum import Enum
import io
from json import JSONDecodeError
from typing import Dict, List, Mapping, Optional
from urllib.parse import urlencode

from speasy.core import http
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.codecs.codecs_registry import get_codec
from speasy.core.hapi.parser import _parse_hapi_csv
from speasy.products.variable import SpeasyVariable

from .exceptions import HapiError, HapiRequestError, HapiServerError, HapiNoData


class HapiEndpoint(Enum):
    CAPABILITIES = "capabilities"
    CATALOG      = "catalog"
    ABOUT        = "about"
    INFO         = "info"
    DATA         = "data"


def _fetch_response(url: str):
    response = http.get(url)
    _check_response(response)
    return response

def _check_hapi_status(data: Dict) -> None:
    code = data["status"]["code"]
    message = data["status"]["message"]
    if code == 1201:
        raise HapiNoData()
    elif 1400 <= code < 1500:
        raise HapiRequestError(code, message)
    elif code >= 1500:
        raise HapiServerError(code, message)

def _check_http_status(status_code: int, text: str) -> None:
    if 400 <= status_code < 500:
        raise HapiRequestError(status_code, text)
    elif status_code >= 500:
        raise HapiServerError(status_code, text)

def _check_response(response) -> None:
    try:
        _check_hapi_status(response.json())
    except (JSONDecodeError, KeyError):
        _check_http_status(response.status_code, response.text)


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


    def _fetch_variables(self, query_parameters: Dict) -> Mapping[str, SpeasyVariable]:
        parameters = query_parameters.get("parameters", [])
        url = self._build_url(HapiEndpoint.DATA, query_parameters)
        f = io.BytesIO(_fetch_response(url).text.encode("utf-8"))
        return _parse_hapi_csv(f, parameters)


    def _build_url(
        self,
        endpoint: Optional[HapiEndpoint] = None,
        query_parameters: Optional[Dict] = None
    ) -> str:
        base = f"{self.server_url}/hapi"
        url = f"{base}/{endpoint.value}" if endpoint else base

        # Flatten "parameters" into a comma-separated query string
        if query_parameters:
            query_params_copy = query_parameters.copy()
            parameters = query_params_copy.get("parameters")
            if parameters:
                query_params_copy["parameters"] = ",".join(parameters)
            else:
                query_params_copy.pop("parameters", None)

            url = f"{url}?{urlencode(query_params_copy)}"

        return url

    def _endpoint_to_json(
            self,
            endpoint: HapiEndpoint,
            query_parameters: Optional[Dict] = None
    ) -> Dict:
        url = self._build_url(endpoint, query_parameters)
        return _fetch_response(url).json()

    def get_hapi(self) -> str:
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
        query_params = {
            self._dataset_param_name: dataset,
        }
        if parameters is not None:
            query_params["parameters"] = parameters  # List[str], will be flatten in _build_url

        return self._endpoint_to_json(HapiEndpoint.INFO, query_params)

    def get_data(
        self, dataset: str, start: str, stop: str, parameters: List[str]
    ) -> Mapping[str, SpeasyVariable]:
        query_params = {
            self._dataset_param_name: dataset,
            "parameters": parameters,
            "start": start,
            "stop": stop,
            "format": "csv",
            "include": "header",
        }
        return self._fetch_variables(query_params)
