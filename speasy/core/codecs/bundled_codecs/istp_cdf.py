from typing import List, AnyStr, Optional, Mapping
import io
from speasy.core.codecs import CodecInterface, register_codec
import pyistp
import re
from datetime import timedelta
from speasy.core.any_files import any_loc_open
from speasy.core.url_utils import urlparse, is_local_file
from speasy.core.cache import CacheCall
from speasy.products import SpeasyVariable, VariableAxis, VariableTimeAxis, DataContainer
import logging

log = logging.getLogger(__name__)


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
        return True
    if axis.attributes.get('DEPEND_0', '') == time_axis_name:
        return True
    return False


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
    if var is not None:
        time_axis_name = var.axes[0].name
        return SpeasyVariable(
            axes=[VariableTimeAxis(values=var.axes[0].values.copy(),
                                   meta=_fix_attributes_types(var.axes[0].attributes))] + [
                     _make_axis(axis, time_axis_name) for axis in var.axes[1:]],
            values=DataContainer(values=var.values.copy(), meta=_fix_attributes_types(var.attributes),
                                 name=var.name,
                                 is_time_dependent=True),
            columns=_build_labels(var))


def _load_variables(variables, file=None, buffer=None, master_file=None, master_buffer=None) -> SpeasyVariable or None:
    istp_loader = pyistp.load(file=file, buffer=buffer, master_file=master_file, master_buffer=master_buffer)
    if istp_loader is not None:
        return {variable: _load_variable(istp_loader, variable) for variable in variables}


def _resolve_url_type(url, prefix="", cache_remote_files=True):
    if url is None:
        return prefix + "file", None
    if type(url) is str:
        if is_local_file(url):
            return prefix + "file", urlparse(url=url).path
        return prefix + "buffer", any_loc_open(url, mode='rb', cache_remote_files=cache_remote_files).read()
    if type(url) is bytes:
        return prefix + "buffer", url
    if hasattr(url, 'read'):
        return prefix + "buffer", url.read()
    return prefix + "file", None


@register_codec
class IstpCdf(CodecInterface):
    """Codec for ISTP CDF files. This codec is a wrapper around PyISTP library. It supports some variations around the ISTP standard."""

    def load_variables(self, variables: List[AnyStr], file: bytes or str or io.IOBase, cache_remote_files=True,
                       master_cdf_url: Optional[bytes or str or io.IOBase] = None, **kwargs) -> Mapping[
                                                                                                    AnyStr, SpeasyVariable] or None:
        kwargs = {
            "variables": variables,
        }
        kwargs.update((_resolve_url_type(file, prefix="", cache_remote_files=cache_remote_files),
                       _resolve_url_type(master_cdf_url, prefix="master_", cache_remote_files=cache_remote_files)))
        return _load_variables(**kwargs)

    @CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
    def load_variable(self, variable: AnyStr, file: bytes or str or io.IOBase, cache_remote_files=True, **kwargs) -> \
    Optional[SpeasyVariable]:
        r = self.load_variables([variable], file, cache_remote_files, **kwargs)
        if r is not None:
            return r.get(variable)

    def save_variables(self, variables: List[SpeasyVariable], file: bytes or str or io.IOBase, **kwargs) -> bool:
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
