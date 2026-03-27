import io
from typing import Optional, Union, Dict, Any

import numpy as np

from speasy.core.codecs.bundled_codecs.hapi.reader import _load_hapi
from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.codec_interface import Buffer



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

def _extract_data_binary(file: io.IOBase, headers: Dict[str, Any]) -> np.ndarray:
    _params = _hapi_header_to_parameters(headers)
    _dtype = _hapi_parameters_to_dtype(_params)
    return np.frombuffer(file.read(), dtype=_dtype)

def load_hapi_binary(file: Union[Buffer, str, io.IOBase]) -> Optional[HapiFile]:
    data, headers = _load_hapi(file, _extract_data_binary)
    hapi_binary_file = HapiFile()
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