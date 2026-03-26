from enum import Enum
import io
from json import JSONDecodeError
from typing import Dict, List, Optional
from urllib.parse import urlencode

from speasy.core import http
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.codecs.codecs_registry import get_codec
from speasy.products.variable import SpeasyVariable

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

    def _data_endpoint_to_spzvar(
            self,
            endpoint: HapiEndpoint,
            query_parameters: Dict
    ) -> List[SpeasyVariable]:
        parameters = query_parameters.get("parameters", []) 
        url = self._build_url(endpoint, query_parameters)
        response = http.get(url)

        if not response.ok:
            try:
                self._check_hapi_status(response.json())
            except ValueError:
                self._check_http_status(response.status_code, response.text)

        if parameters:
            hapi_csv_codec: CodecInterface = get_codec('hapi/csv')
            f = io.StringIO(response.text)
            variables = hapi_csv_codec.load_variables(file=f, variables=parameters, disable_cache=True)
        else:
            raise HapiError(f"Wrong 'parameters' argument to hapi.load_variables: {parameters}")
        return variables

    def _endpoint_to_json(
            self,
            endpoint: HapiEndpoint,
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

    def _build_query_parameters(self, parameters: List[str] = None) -> Dict:
        query_params = {}

        if parameters is not None:
            if isinstance(parameters, str):
                parameters = [parameters]
            query_params["parameters"] = ",".join(parameters)
        return query_params

    def get_info(self, dataset: str, parameters: Optional[List[str]] = None) -> Dict:
        query_params = {
            self._dataset_param_name: dataset,
        }
        if parameters is not None:
            query_params["parameters"] = parameters  # List[str], will be flatten in _build_url

        return self._endpoint_to_json(HapiEndpoint.INFO, query_params)

    def get_data(
        self, dataset: str, start: str, stop: str, parameters: List[str]
    ) -> bytes:
        query_params = {
            self._dataset_param_name: dataset,
            "parameters": parameters,  # List[str], to be flatten in _build_url
            "start": start,
            "stop": stop,
            "format": "csv",
            "include": "header",
        }
        return self._data_endpoint_to_spzvar(HapiEndpoint.DATA, query_params)
