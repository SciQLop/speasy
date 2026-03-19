from typing import List, AnyStr, Optional, Mapping, Union, Dict, Any
import io

from datetime import timedelta
import numpy as np

from speasy.core.codecs import CodecInterface, register_codec
from speasy.core.codecs.bundled_codecs.hapi.codec import _bins_to_axes, _decode_meta, _speasy_variables_to_hapi
from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile, HapiParameter
from speasy.core.codecs.codec_interface import Buffer
from speasy.core.cache import CacheCall
from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer

from .reader import load_hapi_csv
from .writer import save_hapi_csv


def _hapi_csv_to_speasy_variables(hapi_csv_file: HapiFile, variables: List[AnyStr]) -> Mapping[str, SpeasyVariable]:
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
class HapiCsv(CodecInterface):
    """Codec for HAPI CSV files"""

    def load_variables(self, variables: List[AnyStr], file: Union[Buffer, str, io.IOBase], cache_remote_files=True,
                       **kwargs) -> Optional[Mapping[AnyStr, SpeasyVariable]]:
        hapi_csv_file = load_hapi_csv(file)
        if hapi_csv_file is not None:
            return _hapi_csv_to_speasy_variables(hapi_csv_file, variables)
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
        hapi_csv_file = _speasy_variables_to_hapi(variables)
        return save_hapi_csv(hapi_csv_file, file, **kwargs)

    @property
    def supported_extensions(self) -> List[str]:
        return []

    @property
    def supported_mimetypes(self) -> List[str]:
        return []

    @property
    def name(self) -> str:
        return "hapi/csv"
