from itertools import chain, count
from typing import Container, List, Optional, Tuple
import re
import logging

import numpy as np

import pyistp
from pyistp.support_data_variable import SupportDataVariable

from speasy.core.any_files import any_loc_open
from speasy.core.url_utils import urlparse, is_local_file, to_local_path
from speasy.products import SpeasyVariable, VariableAxis, VariableTimeAxis, DataContainer
from speasy.products.variable import _check_extra_axes

log = logging.getLogger(__name__)


def _fix_value_type(value):
    if type(value) in (str, int, float):
        return value
    if type(value) is list:
        return [_fix_value_type(sub_v) for sub_v in value]
    if type(value) is bytes:
        return value.decode('utf-8')
    # netCDF4 gives numpy scalars and arrays where pycdfpp gives Python values
    if isinstance(value, np.generic):
        return _fix_value_type(value.item())
    if isinstance(value, np.ndarray):
        return _fix_value_type(value.tolist())
    return str(value)


def _fix_attributes_types(attributes: dict):
    cleaned = {}
    for key, value in attributes.items():
        cleaned[key] = _fix_value_type(value)
    return cleaned


def _is_time_dependent(axis, time_axis_name, n_records):
    if axis.attributes.get('DEPEND_TIME', '') == time_axis_name:
        return not axis.is_nrv
    if axis.attributes.get('DEPEND_0', '') == time_axis_name:
        return not axis.is_nrv
    if 'DEPEND_TIME' in axis.attributes or 'DEPEND_0' in axis.attributes:
        return False
    # some master CDFs drop DEPEND_0 on record varying support data (SOLO_L2_SWA-EAS-PAD-DEF, see
    # https://github.com/SciQLop/speasy/issues/399), so fall back on the record count
    return not axis.is_nrv and axis.values.shape[0] == n_records


def _display_type(variable: pyistp.loader.DataVariable) -> str:
    if 'DISPLAY_TYPE' in variable.attributes:
        return variable.attributes['DISPLAY_TYPE']
    if 'display_type' in variable.attributes:
        return variable.attributes['display_type']
    return ''


def _make_axis(axis, time_axis_name, n_records):
    return VariableAxis(values=axis.values.copy(), meta=_fix_attributes_types(axis.attributes), name=axis.name,
                        is_time_dependent=_is_time_dependent(axis, time_axis_name, n_records))


def _build_labels(variable: pyistp.loader.DataVariable):
    if variable.labels is None and len(variable.values.shape) != 2:
        return []
    if len(variable.values.shape) != 2:
        return _fix_value_type(variable.labels)
    if type(variable.labels) is list and len(variable.labels) == variable.values.shape[1]:
        return _fix_value_type(variable.labels)
    if type(variable.labels) is list and len(variable.labels) == 1:
        return [f"{variable.labels[0]}[{i}]" for i in range(variable.values.shape[1])]
    return [f"component_{i}" for i in range(variable.values.shape[1])]


def _filter_extra_axes(variable: pyistp.loader.DataVariable) -> List[SupportDataVariable]:
    return variable.axes[1:]


def _axes_fit(time_axis: VariableTimeAxis, axes: List[VariableAxis], values: DataContainer) -> bool:
    try:
        _check_extra_axes(time_axis, axes, values)
        return True
    except (ValueError, IndexError):
        return False


def _fitting_axes(time_axis: VariableTimeAxis, axes: List[VariableAxis], values: DataContainer) -> List[VariableAxis]:
    """The axes before the first one that doesn't fit its data dimension, as CDAWeb's web service does.

    Some masters point DEPEND_1 at the wrong variable (GOES12_EPHEMERIS_SSC/GSM_LAT) and some files write
    an NRV axis with no record (RBSP-A-RBSPICE_LEV-3_TOFXEH/Telescope): the data is still good.
    """
    count = next(n for n in range(len(axes), -1, -1) if _axes_fit(time_axis, axes[:n], values))
    if count < len(axes):
        log.warning(f"Ignoring the axes of {values.name} from {axes[count].name} on: shape {axes[count].shape} "
                    f"does not fit the data shape {values.shape}")
    return axes[:count]


def _valid_variable_or_none(variable: SpeasyVariable) -> Optional[SpeasyVariable]:
    if len(variable) == 1 and variable.time[0] < np.datetime64('1900-01-01'):  # handle fill values in epoch
        return None
    return variable


def _data_variable_or_none(istp_loader: pyistp.loader.ISTPLoader, name: str):
    """pyistp lists the data variables of the master, but a data file may hold only some of them.

    The MMS EPD-EIS masters list the variables of every file version (P4, P5, P6...) and pyistp
    raises a KeyError for the ones a file lacks: that file just has no data for them.
    """
    try:
        return istp_loader.data_variable(name)
    except KeyError:
        log.debug(f"{name} is listed by the master CDF but absent from the data file")
        return None


def _load_variable(istp_loader: pyistp.loader.ISTPLoader, variable) -> SpeasyVariable or None:
    if variable in istp_loader.data_variables():
        var = _data_variable_or_none(istp_loader, variable)
    elif variable.replace('-', '_') in istp_loader.data_variables():  # THX CSA/ISTP
        var = _data_variable_or_none(istp_loader, variable.replace('-', '_'))
    else:  # CDA https://cdaweb.gsfc.nasa.gov/WebServices/REST/#Get_Data_GET
        alternative = re.sub(r"[\\/.%!@#^&*()\-+=`~|?<> ]", "$", variable)
        if alternative in istp_loader.data_variables():
            var = _data_variable_or_none(istp_loader, alternative)
        else:
            return None
    if (var is not None) and (var.values.shape[0] == var.axes[0].values.shape[0]):
        time_axis_name = var.axes[0].name
        time_axis = VariableTimeAxis(values=var.axes[0].values.copy(),
                                     meta=_fix_attributes_types(var.axes[0].attributes))
        values = DataContainer(values=var.values.copy(), meta=_fix_attributes_types(var.attributes), name=var.name,
                               is_time_dependent=True)
        extra_axes = [_make_axis(axis, time_axis_name, len(time_axis)) for axis in _filter_extra_axes(var)]
        return _valid_variable_or_none(SpeasyVariable(
            axes=[time_axis] + _fitting_axes(time_axis, extra_axes, values),
            values=values,
            columns=_build_labels(var)))
    return None


def _resolve_url_type(url, prefix="", cache_remote_files=True, max_age=None):
    if url is None:
        return prefix + "file", None
    if type(url) is str:
        if is_local_file(url):
            return prefix + "file", to_local_path(url)
        return prefix + "buffer", any_loc_open(url, mode='rb', cache_remote_files=cache_remote_files,
                                               max_age=max_age).read()
    if type(url) in (memoryview, bytes):
        return prefix + "buffer", bytes(url)
    if hasattr(url, 'read'):
        return prefix + "buffer", url.read()
    return prefix + "file", None


def _list_variables(file) -> list:
    key, value = _resolve_url_type(file)
    istp_loader = pyistp.load(**{key: value})
    if istp_loader is not None:
        return istp_loader.data_variables()
    return []


def _simplify_shape(values: np.ndarray) -> np.ndarray:
    if len(values.shape) == 2 and values.shape[1] == 1:
        return np.reshape(values, (-1))
    return values


def _free_name(name: str, *taken: Container[str]) -> str:
    candidates = chain([name], (f"{name}_{i}" for i in count(1)))
    return next(candidate for candidate in candidates if not any(candidate in names for names in taken))


def _axis_slot(axis: VariableAxis, saved_axes: List[Tuple[VariableAxis, str]], taken: Container[str]) -> Tuple[str, bool]:
    """The name to write an axis under, and whether it still has to be written.

    An axis equal to one already saved shares it; one that only shares its name gets a free name instead.
    """
    for saved, name in saved_axes:
        if saved == axis:
            return name, False
    name = _free_name(axis.name, taken, [name for _, name in saved_axes])
    saved_axes.append((axis, name))
    return name, True


def _label_attributes(v: SpeasyVariable) -> dict:
    """The ISTP attributes the reader turns back into the columns of a 2D variable."""
    if v.values.ndim != 2 or len(v.columns) != v.values.shape[1]:
        return {}
    if v.values.shape[1] == 1:
        return {"LABLAXIS": v.columns[0]}
    return {"LABL_PTR_1": list(v.columns)}


def _attributes_to_write(v: SpeasyVariable) -> dict:
    """The variable's meta as written: the reader only lists variables with VAR_TYPE 'data'."""
    return {"VAR_TYPE": "data", **v.meta, **_label_attributes(v)}
