from typing import List, AnyStr, Optional, Mapping, Union
import io
import re
import logging

from datetime import timedelta
import numpy as np

import pyistp
from pyistp.support_data_variable import SupportDataVariable

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


def _load_variables(variables, file=None, buffer=None) -> SpeasyVariable or None:
    istp_loader = pyistp.load_netcdf(file=file, buffer=buffer)
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
