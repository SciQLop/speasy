from datetime import timedelta
import io
import logging
from typing import AnyStr, List, Mapping, Optional, Union, Dict, Any

import numpy as np


from speasy.core.cache._function_cache import CacheCall
from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.codecs.codecs_registry import register_codec
from speasy.core.codecs.codec_interface import Buffer
from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products.variable import SpeasyVariable

log = logging.getLogger(__name__)
from .reader import load_hapi_binary

def _decode_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    if "units" in meta:
        meta["UNITS"] = meta.pop("units")
    return meta

def _bin_to_axis(json_bin: Dict[str, Any], hap_csv_file: HapiFile) -> VariableAxis:
    centers = json_bin.get("centers")
    name = json_bin.get("name", "bin_axis")
    if centers is None:
        raise ValueError("Invalid bin specification: missing 'centers' field")
    if isinstance(centers, str):
        hapi_parameter = hap_csv_file.get_parameter(centers)
        _meta = _decode_meta(hapi_parameter.meta)
        variable_axis = VariableAxis(values=hapi_parameter.values,
                                     meta=_meta,
                                     is_time_dependent=True,
                                     name=name)
    elif isinstance(centers, list):
        try:
            axis_values = np.array(centers, dtype=float)
        except ValueError:
            raise ValueError("Invalid bin specification: 'centers' list must contain numeric values")
        variable_axis = VariableAxis(values=axis_values,
                                     meta={"name": "centers", "UNITS": json_bin.get("units", None)},
                                     is_time_dependent=False,
                                     name=name)
    else:
        raise ValueError("Invalid bin specification: 'centers' must be either a string or a list")
    return variable_axis


def _bins_to_axes(json_bins: List[Dict[str, Any]], hap_csv_file: HapiFile) -> List[VariableAxis]:
    axes = []
    for json_bin in json_bins:
        try:
            axis = _bin_to_axis(json_bin, hap_csv_file)
            axes.append(axis)
        except ValueError as e:
            log.warning(f"Skipping invalid bin specification: {e}")
    return axes

def _hapi_binary_to_speasy_variables(hapi_csv_file: HapiFile, variables: List[AnyStr]) -> Mapping[str, SpeasyVariable]:
    time_axis = VariableTimeAxis(values=hapi_csv_file.time_axis, meta=hapi_csv_file.time_axis_meta)
    loaded_vars = {}
    for var_name in variables:
        parameter = hapi_csv_file.get_parameter(var_name)
        if parameter is None:
            continue
        _axes = [time_axis]
        if 'bins' in parameter.meta.keys():
            _axes.extend(_bins_to_axes(parameter.meta.get("bins", []), hapi_csv_file))
        loaded_vars[var_name] = SpeasyVariable(axes=_axes, values=DataContainer(parameter.values,
                                                                                name=parameter.name,
                                                                                meta=_decode_meta(
                                                                                parameter.meta)))
    return loaded_vars

@register_codec
class HapiBinary(CodecInterface):
    """Codec for HAPI Binary files"""

    def load_variables(self, variables: List[AnyStr], file: Union[Buffer, str, io.IOBase], cache_remote_files=True,
                       **kwargs) -> Optional[Mapping[AnyStr, SpeasyVariable]]:
        hapi_binary_file = load_hapi_binary(file)
        if hapi_binary_file is not None:
            return _hapi_binary_to_speasy_variables(hapi_binary_file, variables)
        return None

    @CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
    def load_variable(self,
                      variable: AnyStr, file: Union[Buffer, str, io.IOBase],
                      cache_remote_files=True,
                      **kwargs
                      ) -> Optional[SpeasyVariable]:
        return self.load_variables([variable], file, cache_remote_files)[variable]

    def save_variables(self,
                       variables: List[SpeasyVariable],
                       file: Optional[Union[str, io.IOBase]] = None,
                       **kwargs
                       ) -> Union[bool, Buffer]:
        # hapi_binary_file = _speasy_variables_to_hapi_binary(variables)
        # return save_hapi_binary(hapi_binary_file, file)
        return True

    @property
    def supported_extensions(self) -> List[str]:
        return []

    @property
    def supported_mimetypes(self) -> List[str]:
        return []

    @property
    def name(self) -> str:
        return "hapi/binary"
