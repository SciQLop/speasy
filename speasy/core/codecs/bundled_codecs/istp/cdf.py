from typing import List, AnyStr, Optional, Mapping, Union
import io
import logging
from datetime import timedelta

import numpy as np
import pycdfpp
import pyistp

from speasy.core.codecs import CodecInterface, register_codec, Buffer
from speasy.core.cache import CacheCall
from speasy.products import SpeasyVariable, VariableAxis

from . import _PTR_rx, _load_variable, _resolve_url_type, _simplify_shape

log = logging.getLogger(__name__)


def _load_variables(variables, file=None, buffer=None, master_file=None, master_buffer=None):
    istp_loader = pyistp.load(file=file, buffer=buffer, master_file=master_file, master_buffer=master_buffer)
    if istp_loader is not None:
        return {variable: _load_variable(istp_loader, variable) for variable in variables}
    return None


def _convert_attributes_to_variables(variable_name: str, attrs: Mapping, cdf: pycdfpp.CDF):
    clean_attrs = {}
    for name, attr_v in attrs.items():
        target_name = f"{variable_name}_{name}_{variable_name}"
        if _PTR_rx.match(name):
            cdf.add_variable(
                name=target_name,
                values=attr_v
            )
            clean_attrs[name] = target_name
        else:
            clean_attrs[name] = attr_v
    return clean_attrs


def _write_axis(ax: VariableAxis, cdf: pycdfpp.CDF, compress_variables=False) -> bool:
    data_type = None
    if ax.values.dtype == np.dtype("datetime64[ns]"):
        data_type = pycdfpp.DataType.CDF_TIME_TT2000
    cdf.add_variable(
        name=ax.name,
        values=_simplify_shape(ax.values),
        data_type=data_type,
        compression=pycdfpp.CompressionType.gzip_compression if compress_variables else pycdfpp.CompressionType.no_compression
    )
    return True


def _write_variable(v: SpeasyVariable, cdf: pycdfpp.CDF, already_saved_axes: List[VariableAxis],
                    compress_variables=False) -> None:
    def _already_in_cdf(ax: VariableAxis):
        for _ax in already_saved_axes:
            if _ax == ax:
                return _ax.name
        return None

    depends = {}
    for index, ax in enumerate(v.axes):
        a = _already_in_cdf(ax)
        if a is None:
            _write_axis(ax, cdf, compress_variables)
            depends[f"DEPEND_{index}"] = ax.name
            already_saved_axes.append(ax)
        else:
            depends[f"DEPEND_{index}"] = a
    attributes = v.meta
    attributes.update(depends)
    cdf.add_variable(
        name=v.name,
        values=_simplify_shape(v.values),
        attributes=_convert_attributes_to_variables(variable_name=v.name, attrs=attributes, cdf=cdf),
        compression=pycdfpp.CompressionType.gzip_compression if compress_variables else pycdfpp.CompressionType.no_compression
    )


@register_codec
class IstpCdf(CodecInterface):
    """Codec for ISTP CDF files. This codec is a wrapper around PyISTP library. It supports some variations around the ISTP standard."""

    def load_variables(self,
                       variables: List[AnyStr],
                       file: Union[Buffer, str, io.IOBase],
                       cache_remote_files=True,
                       master_cdf_url: Optional[Union[Buffer, str, io.IOBase]] = None,
                       **kwargs
                       ) -> Optional[Mapping[AnyStr, SpeasyVariable]]:
        kwargs["variables"] = variables
        kwargs.update((_resolve_url_type(file, prefix="", cache_remote_files=cache_remote_files),
                       _resolve_url_type(master_cdf_url, prefix="master_", cache_remote_files=cache_remote_files)))
        return _load_variables(**kwargs)

    @CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
    def load_variable(self,
                      variable: AnyStr, file: Union[Buffer, str, io.IOBase],
                      cache_remote_files=True,
                      master_cdf_url: Optional[Union[Buffer, str, io.IOBase]] = None,
                      **kwargs
                      ) -> Optional[SpeasyVariable]:
        r = self.load_variables(variables=[variable], file=file, master_cdf_url=master_cdf_url,
                                cache_remote_files=cache_remote_files, **kwargs)
        if r is not None:
            return r.get(variable)
        return None

    def save_variables(self,
                       variables: List[SpeasyVariable],
                       file: Optional[Union[str, io.IOBase]] = None,
                       compress_variables=False,
                       **kwargs
                       ) -> Union[bool, Buffer]:
        cdf = pycdfpp.CDF()
        axes = []
        for variable in variables:
            if not isinstance(variable, SpeasyVariable):
                raise ValueError(f"Expected SpeasyVariable, got {type(variable)}")
            _write_variable(variable, cdf, axes, compress_variables)
        if type(file) is str:
            pycdfpp.save(cdf, file)
            return True
        elif isinstance(file, io.IOBase):
            file.write(pycdfpp.save(cdf))
            return True
        elif file is None:
            return memoryview(pycdfpp.save(cdf))
        return False

    @property
    def supported_extensions(self) -> List[str]:
        return ["cdf"]

    @property
    def supported_mimetypes(self) -> List[str]:
        return ["application/x-cdf"]

    @property
    def name(self) -> str:
        return self.__class__.__name__
