from typing import Optional, Union, Dict, Any, Tuple
import io
import logging

import numpy as np
import pandas as pds
import json

from speasy.core.codecs.codec_interface import Buffer
from speasy.core.any_files import any_loc_open
from .csv_file import HapiCsvFile

log = logging.getLogger(__name__)


def _extract_headers(file: io.IOBase) -> Dict[str, Any]:
    headers = []
    line = file.readline()
    while line:
        if line.startswith('#'):
            headers.append(line[1:].strip())
        else:
            break
        line = file.readline()
    if len(headers):
        return json.loads(''.join(headers))
    return {}


def _extract_data(file: io.IOBase) -> pds.DataFrame:
    file.seek(0)
    return pds.read_csv(file, comment='#', sep=',', header=None, skiprows=0, parse_dates=[0], index_col=0)


def _parse_hapi_csv(file: io.IOBase) -> Tuple[pds.DataFrame, Dict[str, Any]]:
    headers = _extract_headers(file)
    assert headers["parameters"][0]["type"] == "isotime"
    data = _extract_data(file)
    return data, headers


def _load_csv(file: Union[Buffer, str, io.IOBase]) -> Tuple[Optional[pds.DataFrame], Optional[Dict[str, Any]]]:
    if isinstance(file, str):
        with any_loc_open(file, cache_remote_files=False, mode='r') as f:
            return _parse_hapi_csv(f)
    if isinstance(file, io.IOBase) or hasattr(file, 'read'):
        return _parse_hapi_csv(file)
    return None, None


def load_hapi_csv(file: Union[Buffer, str, io.IOBase]) -> Optional[HapiCsvFile]:
    data, headers = _load_csv(file)
    hapi_csv_file = HapiCsvFile()
    if data is not None and headers is not None:
        time_header = headers["parameters"][0]
        assert time_header["type"] == "isotime"
        hapi_csv_file.create_parameter(data.index.to_numpy(dtype="datetime64[ns]"),
                                       meta=time_header)
        column_offset = 0
        for i, param_meta in enumerate(headers["parameters"][1:]):
            shape = param_meta.get("size", [1])
            flatten_shape = np.prod(shape)
            hapi_csv_file.create_parameter(data.iloc[:, column_offset:column_offset + flatten_shape].to_numpy().reshape(
                [len(data.index)] + shape), meta=param_meta)
            column_offset += flatten_shape
        return hapi_csv_file
    return None
