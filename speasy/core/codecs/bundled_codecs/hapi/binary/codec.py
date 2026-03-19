from datetime import timedelta
import io
from typing import AnyStr, List, Mapping, Optional, Union, Dict, Any

import numpy as np


from speasy.core.cache._function_cache import CacheCall
from speasy.core.codecs.bundled_codecs.hapi.codec import _bins_to_axes, _decode_meta, _speasy_variables_to_hapi
from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.codecs.codecs_registry import register_codec
from speasy.core.codecs.codec_interface import Buffer
from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products.variable import SpeasyVariable

from .reader import load_hapi_binary

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
        hapi_binary_file = _speasy_variables_to_hapi(variables)
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
