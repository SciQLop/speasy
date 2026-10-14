from enum import Enum
import io
import json
import re
from typing import Dict, List, Mapping, Optional
from urllib.parse import urlencode

from speasy.core import http
from speasy.core.codecs.codecs_registry import get_codec
from speasy.products.variable import SpeasyVariable

from .registry import blocked_reason
from .exceptions import (
    HapiRequestError, HapiServerError, HapiNoData
)


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
    # Error pages can be whole HTML documents
    text = text if len(text) <= 300 else f"{text[:300]}…"
    if 400 <= status_code < 500:
        raise HapiRequestError(status_code, text)
    elif status_code >= 500:
        raise HapiServerError(status_code, text)


def _check_response(response) -> None:
    try:
        _check_hapi_status(response.json())
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
        _check_http_status(response.status_code, response.text)


def _check_data_response(response) -> None:
    """A data body is CSV or binary, so only an error response is worth parsing as a HAPI status."""
    if not response.ok:
        _check_response(response)
        _check_http_status(response.status_code, response.text)


def _hapi_base_url(server_url: str) -> str:
    """Registry URLs end with '/hapi', older code passes the server root."""
    url = server_url.rstrip('/')
    return url if url.endswith('/hapi') else f"{url}/hapi"


def _header_for(header: Mapping, parameters: List[str]) -> Dict:
    """The data columns are the time column then the requested parameters, in /info order."""
    wanted = set(parameters)
    columns = [p for i, p in enumerate(header["parameters"]) if i == 0 or p["name"] in wanted]
    return {**header, "parameters": columns}


def _prepend_header(header: Mapping, body: bytes) -> io.BytesIO:
    return io.BytesIO(b"#" + json.dumps(header).encode("utf-8") + b"\n" + body)


class HapiClient:
    def __init__(self, server_url: str):
        self.base_url = _hapi_base_url(server_url)
        if (reason := blocked_reason(self.base_url)) is not None:
            raise ValueError(reason)
        self.capabilities = self.get_capabilities()
        self.is_v3 = self._is_v3(self.capabilities.get("HAPI"))

    @property
    def server_url(self) -> str:
        return self.base_url[:-len('/hapi')]

    @staticmethod
    def _is_v3(version: Optional[str]) -> bool:
        major = re.match(r'\D*(\d+)', version or '')
        if major is None or int(major[1]) not in (1, 2, 3):
            raise RuntimeError(f"Unsupported HAPI version {version!r}: Speasy supports HAPI 1.x to 3.x. Stop listing "
                               f"this server with the [HAPI] disabled_servers config entry")
        return int(major[1]) == 3

    @property
    def _dataset_key(self) -> str:
        """Starting from HAPI-3.0, the 'id' parameter becomes 'dataset' (1.x queries are those of 2.x)"""
        return "dataset" if self.is_v3 else "id"

    @property
    def _time_keys(self) -> tuple:
        """Starting from HAPI-3.0, 'time.min'/'time.max' become 'start'/'stop'"""
        return ("start", "stop") if self.is_v3 else ("time.min", "time.max")

    def _build_url(
        self,
        endpoint: Optional[HapiEndpoint] = None,
        query_parameters: Optional[Dict] = None
    ) -> str:
        url = f"{self.base_url}/{endpoint.value}" if endpoint else self.base_url

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

    def _data_format(self, header: Mapping) -> str:
        # The binary reader can't decode string parameters, CSV can always be used.
        has_strings = any(p.get("type") == "string" for p in header["parameters"][1:])
        return "binary" if "binary" in self.capabilities.get("outputFormats", []) and not has_strings else "csv"

    def get_hapi(self) -> str:
        url = self._build_url()
        with http.urlopen(url) as response:
            html_page = response.text
        return html_page

    def get_capabilities(self) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.CAPABILITIES)

    def get_catalog(self, depth: Optional[str] = None) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.CATALOG, {"depth": depth} if depth else None)

    def get_about(self) -> Dict:
        return self._endpoint_to_json(HapiEndpoint.ABOUT)

    def get_info(self, dataset: str, parameters: Optional[List[str]] = None) -> Dict:
        query_params = {
            self._dataset_key: dataset,
        }
        if parameters is not None:
            query_params["parameters"] = parameters  # List[str], will be flatten in _build_url

        return self._endpoint_to_json(HapiEndpoint.INFO, query_params)

    def get_data(
        self, dataset: str, start: str, stop: str, parameters: List[str], header: Optional[Mapping] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Mapping[str, SpeasyVariable]:
        """Downloads ``parameters`` without the server's header, then decodes them with ``header``: the /info
        response of ``dataset``, fetched when not given. Some servers reject ``include=header``."""
        header = _header_for(header if header is not None else self.get_info(dataset, parameters), parameters)
        data_format = self._data_format(header)
        start_key, stop_key = self._time_keys
        url = self._build_url(HapiEndpoint.DATA, {
            self._dataset_key: dataset,
            "parameters": parameters,
            start_key: start,
            stop_key: stop,
            "format": data_format,
        })
        response = http.get(url, headers=headers)
        _check_data_response(response)
        return get_codec(f"hapi/{data_format}").load_variables(
            file=_prepend_header(header, response.bytes), variables=parameters, disable_cache=True)
