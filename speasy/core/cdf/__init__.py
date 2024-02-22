import io

import pyistp
import re
from ..any_files import any_loc_open
from ..url_utils import urlparse, is_local_file
from ...products import SpeasyVariable, VariableAxis, VariableTimeAxis, DataContainer


def _fix_value_type(value):
    if type(value) in (str, int, float):
        return value
    if type(value) is list:
        return [_fix_value_type(sub_v) for sub_v in value]
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
        return variable.labels
    if type(variable.labels) is list and len(variable.labels) == variable.values.shape[1]:
        return variable.labels
    if type(variable.labels) is list and len(variable.labels) == 1:
        return [f"{variable.labels[0]}[{i}]" for i in range(variable.values.shape[1])]
    return [f"component_{i}" for i in range(variable.values.shape[1])]


def _load_variable(variable="", file=None, buffer=None) -> SpeasyVariable or None:
    istp = pyistp.load(file=file, buffer=buffer)
    if istp is not None:
        if variable in istp.data_variables():
            var = istp.data_variable(variable)
        elif variable.replace('-', '_') in istp.data_variables():  # THX CSA/ISTP
            var = istp.data_variable(variable.replace('-', '_'))
        else:  # CDA https://cdaweb.gsfc.nasa.gov/WebServices/REST/#Get_Data_GET
            alternative = re.sub(r"[\\/.%!@#^&*()\-+=`~|?<> ]", "$", variable)
            if alternative in istp.data_variables():
                var = istp.data_variable(alternative)
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
    return None


def load_variable(variable, file: bytes or str or io.IOBase, cache_remote_files=True) -> SpeasyVariable or None:
    if type(file) is str:
        if is_local_file(file):
            return _load_variable(variable=variable, file=urlparse(url=file).path)
        return _load_variable(variable=variable,
                              buffer=any_loc_open(file, mode='rb', cache_remote_files=cache_remote_files).read())
    if type(file) is bytes:
        return _load_variable(variable=variable, buffer=bytes)
    if hasattr(file, 'read'):
        return _load_variable(variable=variable, buffer=file.read())
    return None
