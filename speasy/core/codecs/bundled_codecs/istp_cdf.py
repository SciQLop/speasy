from typing import List, AnyStr, Optional, Mapping, Union
import io
import re
import logging

from datetime import timedelta
import numpy as np

import pyistp
from pyistp.support_data_variable import SupportDataVariable
import pycdfpp

from speasy.core.codecs import CodecInterface, register_codec, Buffer
from speasy.core.any_files import any_loc_open
from speasy.core.url_utils import urlparse, is_local_file
from speasy.core.cache import CacheCall
from speasy.products import SpeasyVariable, VariableAxis, VariableTimeAxis, DataContainer

log = logging.getLogger(__name__)
_PTR_rx = re.compile(r".*_PTR(_\d+)?")


def _fix_value_type(value):
    if type(value) in (str, int, float):
        return value
    if type(value) is list:
        return [_fix_value_type(sub_v) for sub_v in value]
    if type(value) is bytes:
        return value.decode('utf-8')
    return str(value)


def _fix_attributes_types(attributes: dict):
    cleaned = {}
    for key, value in attributes.items():
        cleaned[key] = _fix_value_type(value)
    return cleaned


def _is_time_dependent(axis, time_axis_name):
    if axis.attributes.get('DEPEND_TIME', '') == time_axis_name:
        return not axis.is_nrv
    if axis.attributes.get('DEPEND_0', '') == time_axis_name:
        return not axis.is_nrv
    return False


def _display_type(variable: pyistp.loader.DataVariable) -> str:
    if 'DISPLAY_TYPE' in variable.attributes:
        return variable.attributes['DISPLAY_TYPE']
    if 'display_type' in variable.attributes:
        return variable.attributes['display_type']
    return ''


def _make_axis(axis, time_axis_name):
    return VariableAxis(values=axis.values.copy(), meta=_fix_attributes_types(axis.attributes), name=axis.name,
                        is_time_dependent=_is_time_dependent(axis, time_axis_name))


def _build_labels(variable: pyistp.loader.DataVariable):
    if len(variable.values.shape) != 2:
        return _fix_value_type(variable.labels)
    if type(variable.labels) is list and len(variable.labels) == variable.values.shape[1]:
        return _fix_value_type(variable.labels)
    if type(variable.labels) is list and len(variable.labels) == 1:
        return [f"{variable.labels[0]}[{i}]" for i in range(variable.values.shape[1])]
    return [f"component_{i}" for i in range(variable.values.shape[1])]


def _filter_extra_axes(variable: pyistp.loader.DataVariable) -> List[SupportDataVariable]:
    return variable.axes[1:]


def _valid_variable_or_none(variable: SpeasyVariable) -> Optional[SpeasyVariable]:
    if len(variable) == 1 and variable.time[0] < np.datetime64('1900-01-01'):  # handle fill values in epoch
        return None
    return variable


def _load_variable(istp_loader: pyistp.loader.ISTPLoader, variable) -> SpeasyVariable or None:
    if variable in istp_loader.data_variables():
        var = istp_loader.data_variable(variable)
    elif variable.replace('-', '_') in istp_loader.data_variables():  # THX CSA/ISTP
        var = istp_loader.data_variable(variable.replace('-', '_'))
    else:  # CDA https://cdaweb.gsfc.nasa.gov/WebServices/REST/#Get_Data_GET
        alternative = re.sub(r"[\\/.%!@#^&*()\-+=`~|?<> ]", "$", variable)
        if alternative in istp_loader.data_variables():
            var = istp_loader.data_variable(alternative)
        else:
            return None
    if (var is not None) and (var.values.shape[0] == var.axes[0].values.shape[0]):
        time_axis_name = var.axes[0].name
        return _valid_variable_or_none(SpeasyVariable(
            axes=[VariableTimeAxis(values=var.axes[0].values.copy(),
                                   meta=_fix_attributes_types(var.axes[0].attributes))] + [
                     _make_axis(axis, time_axis_name) for axis in _filter_extra_axes(var)],
            values=DataContainer(values=var.values.copy(), meta=_fix_attributes_types(var.attributes),
                                 name=var.name,
                                 is_time_dependent=True),
            columns=_build_labels(var)))
    return None


def _load_variables(variables, file=None, buffer=None, master_file=None, master_buffer=None) -> SpeasyVariable or None:
    istp_loader = pyistp.load(file=file, buffer=buffer, master_file=master_file, master_buffer=master_buffer)
    if istp_loader is not None:
        return {variable: _load_variable(istp_loader, variable) for variable in variables}
    return None


def _resolve_url_type(url, prefix="", cache_remote_files=True):
    if url is None:
        return prefix + "file", None
    if type(url) is str:
        if is_local_file(url):
            return prefix + "file", urlparse(url=url).path
        return prefix + "buffer", any_loc_open(url, mode='rb', cache_remote_files=cache_remote_files).read()
    if type(url) in (memoryview, bytes):
        return prefix + "buffer", url
    if hasattr(url, 'read'):
        return prefix + "buffer", url.read()
    return prefix + "file", None


def _simplify_shape(values: np.ndarray) -> np.ndarray:
    if len(values.shape) == 2 and values.shape[1] == 1:
        return np.reshape(values, (-1))
    return values


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
                    compress_variables=False) -> bool:
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
            depends[f"DEPEND_{index}"] = a.name
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
        elif hasattr(file, 'write'):
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
