from typing import List, AnyStr, Optional, Mapping, Union
import io
import logging
from datetime import timedelta

import pyistp

from speasy.core.codecs import CodecInterface, register_codec, Buffer
from speasy.core.cache import CacheCall
from speasy.products import SpeasyVariable

from . import _load_variable, _resolve_url_type

log = logging.getLogger(__name__)


def _load_variables(variables, file=None, buffer=None):
    istp_loader = pyistp.load_netcdf(file=file, buffer=buffer)
    if istp_loader is not None:
        return {variable: _load_variable(istp_loader, variable) for variable in variables}
    return None


@register_codec
class IstpNetCDF(CodecInterface):
    """Codec for ISTP NetCDF4 files. This codec is a wrapper around PyISTP library using the NetCDF4 driver."""

    def load_variables(self,
                       variables: List[AnyStr],
                       file: Union[Buffer, str, io.IOBase],
                       cache_remote_files=True,
                       **kwargs
                       ) -> Optional[Mapping[AnyStr, SpeasyVariable]]:
        kwargs["variables"] = variables
        kwargs.update((_resolve_url_type(file, prefix="", cache_remote_files=cache_remote_files),))
        return _load_variables(**kwargs)

    @CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
    def load_variable(self,
                      variable: AnyStr, file: Union[Buffer, str, io.IOBase],
                      cache_remote_files=True,
                      **kwargs
                      ) -> Optional[SpeasyVariable]:
        r = self.load_variables(variables=[variable], file=file,
                                cache_remote_files=cache_remote_files, **kwargs)
        if r is not None:
            return r.get(variable)
        return None

    def save_variables(self, variables: List[SpeasyVariable], file: Optional[Union[str, io.IOBase]] = None,
                       **kwargs) -> Union[bool, Buffer]:
        raise NotImplementedError("NetCDF write support not yet implemented")

    @property
    def supported_extensions(self) -> List[str]:
        return ["nc", "nc4"]

    @property
    def supported_mimetypes(self) -> List[str]:
        return ["application/x-netcdf", "application/netcdf"]

    @property
    def name(self) -> str:
        return self.__class__.__name__
