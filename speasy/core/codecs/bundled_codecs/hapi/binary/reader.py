from ast import Tuple
import io
import json
from typing import Optional, Union, Dict, Any, Tuple

import numpy as np

from speasy.core.any_files import any_loc_open
from speasy.core.codecs.bundled_codecs.hapi.binary.binary_file import HapiBinaryFile
from speasy.core.codecs.codec_interface import Buffer

def _extract_headers(file: io.IOBase) -> Dict[str, Any]:
    file.seek(0)
    header_lines = []
    while True:
        line = file.readline()
        if not line.startswith(b"#"):
            break
        header_lines.append(line[1:])

    if not header_lines:
        return None

    header_bytes = b"".join(header_lines)
    return json.loads(header_bytes.decode("utf-8"))


def _hapi_header_to_parameters(header):
    hapi_parameters = []
    for param in header["parameters"]:
        hapi_parameters.append({
            "name": param.get("name", None),
            "type": param.get("type", None),
            "length": param.get("length", None),
            "size": param.get("size", None),
        })
    return hapi_parameters


def _hapi_parameters_to_dtype(hapi_parameters):
    fields = []
    for p in hapi_parameters:
        _name = p["name"]
        _type = p["type"]
        _size = p["size"] or [1]
        _shape = tuple(_size)

        if _type == "isotime" or _type == "string":
            fields.append((_name, f'S{p["length"]}'))
        elif _type == "double":
            fields.append((_name, "<f8", _shape))
        elif _type == "integer":
            fields.append((_name, "<i4", _shape))

    return np.dtype(fields)

def _extract_data(file: io.IOBase, headers):
    file.seek(0)
    _params = _hapi_header_to_parameters(headers)
    _dtype = _hapi_parameters_to_dtype(_params)
    file.seek(len(file.readline()))  # Skip header line
    data = file.read()
    data = np.frombuffer(data, dtype=_dtype)
    return data

def _parse_hapi_binary(file: io.IOBase) -> Tuple[np.array, Dict[str, Any]]:
    headers = _extract_headers(file)
    assert headers["parameters"][0]["type"] == "isotime"
    data = _extract_data(file, headers)
    return data, headers

def _load_binary(file: Union[Buffer, str, io.IOBase]) -> Tuple[Optional[np.array], Optional[Dict[str, Any]]]:
    if isinstance(file, str):
        with any_loc_open(file, cache_remote_files=False, mode='br') as f:
            return _parse_hapi_binary(f)
    if isinstance(file, io.IOBase) or hasattr(file, 'read'):
        return _parse_hapi_binary(file)
    return None, None


def load_hapi_binary(file: Union[Buffer, str, io.IOBase]) -> Optional[HapiBinaryFile]:
    data, headers = _load_binary(file)
    hapi_binary_file = HapiBinaryFile()
    if data is not None and headers is not None:
        time_header = headers["parameters"][0]
        assert time_header["type"] == "isotime"
        data_time = np.char.rstrip(data["Time"].astype("U24"), "Z").astype("datetime64[ns]")
        hapi_binary_file.create_parameter(data_time,
                                       meta=time_header)
        for i, param_meta in enumerate(headers["parameters"][1:]):
            hapi_binary_file.create_parameter(data[param_meta["name"]]
                , meta=param_meta)
        return hapi_binary_file
    return None