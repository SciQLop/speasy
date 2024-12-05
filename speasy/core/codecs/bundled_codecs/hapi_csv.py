from typing import List, AnyStr, Optional, Mapping, Union, Dict, Any, Tuple
import io
import logging

from datetime import timedelta

import numpy as np
import pandas as pds
import json

from speasy.core.codecs import CodecInterface, register_codec, Buffer
from speasy.core.any_files import any_loc_open
from speasy.core.cache import CacheCall
from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer

log = logging.getLogger(__name__)


def _encode_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    if "UNITS" in meta:
        meta["units"] = meta.pop("UNITS")
    return meta


def _decode_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    if "units" in meta:
        meta["UNITS"] = meta.pop("units")
    return meta


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
    return pds.read_csv(file, comment='#', header=None, skiprows=0)

def _parse_HAPI_csv(file: io.IOBase) -> Tuple[pds.DataFrame, Dict[str, Any]]:
    headers = _extract_headers(file)
    data = _extract_data(file)
    return data, headers

def _load_csv(file: Union[Buffer, str, io.IOBase], **kwargs) -> Tuple[
    Optional[pds.DataFrame], Optional[Dict[str, Any]]]:
    if isinstance(file, str):
        with any_loc_open(file, cache_remote_files=False, mode='r') as f:
            return _parse_HAPI_csv(f)
    if isinstance(file, io.IOBase) or hasattr(file, 'read'):
        return _parse_HAPI_csv(file)
    return None, None


def _load_variables(file: Union[Buffer, str, io.IOBase], variables: List[AnyStr]) -> Optional[
    Mapping[AnyStr, SpeasyVariable]]:
    data, headers = _load_csv(file)
    if data is not None and headers is not None:
        assert headers["parameters"][0]["type"] == "isotime"
        time_axis = VariableTimeAxis(data.index.to_numpy(dtype="datetime64[ns]"), meta=headers["parameters"][0])
        extracted_variables = {}
        column_offset = 1
        for i, param in enumerate(headers["parameters"][1:]):
            shape = param.get("size", [1])
            flatten_shape = np.prod(shape)
            if param["name"] in variables:
                extracted_variables[param["name"]] = SpeasyVariable(
                    axes=[time_axis],
                    values=DataContainer(
                        values=data.iloc[:, column_offset:column_offset + flatten_shape].to_numpy().reshape(
                            [len(time_axis)] + shape), meta=_decode_meta(param)))
            column_offset += flatten_shape
        return extracted_variables
    return None


@register_codec
class HAPI_CSV(CodecInterface):
    """Codec for HAPI CSV files"""

    def load_variables(self, variables: List[AnyStr], file: Union[Buffer, str, io.IOBase], cache_remote_files=True,
                       **kwargs) -> Optional[Mapping[AnyStr, SpeasyVariable]]:
        return _load_variables(file, variables)

    @CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
    def load_variable(self,
                      variable: AnyStr, file: Union[Buffer, str, io.IOBase],
                      cache_remote_files=True,
                      **kwargs
                      ) -> Optional[SpeasyVariable]:
        return _load_variables(file, [variable])[variable]

    def save_variables(self,
                       variables: List[SpeasyVariable],
                       file: Optional[Union[str, io.IOBase]] = None,
                       **kwargs
                       ) -> Union[bool, Buffer]:
        return False

    @property
    def supported_extensions(self) -> List[str]:
        return []

    @property
    def supported_mimetypes(self) -> List[str]:
        return []

    @property
    def name(self) -> str:
        return "hapi/csv"
