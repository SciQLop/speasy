from datetime import timedelta

import numpy as np

from typing import Any, AnyStr, Dict, List, Mapping

from speasy.core.cache._function_cache import CacheCall
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products.variable import SpeasyVariable, same_time_axis

from .hapi_file import HapiFile, HapiParameter

import logging
log = logging.getLogger(__name__)

def _time_dependent_axis_name(ax: VariableAxis) -> str:
    return f"{ax.name}_centers_time_varying"

def _get_variable_axes(variable: SpeasyVariable, is_time_dependent: bool) -> List[VariableAxis]:
    return [ax for ax in variable.axes[1:] if ax.is_time_dependent == is_time_dependent]

def _decode_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    if "units" in meta:
        meta["UNITS"] = meta.pop("units")
    return meta

def _make_hapi_time_axis(time_axis: VariableTimeAxis) -> HapiParameter:
    return HapiParameter(values=time_axis.values,
                            meta={"name": "Time", "type": "isotime", "units": "UTC", "length": 24, "fill": None})

def _make_hapi_parameter(variable: SpeasyVariable) -> HapiParameter:
    return HapiParameter(values=variable.values,
                            meta=_create_meta(variable))

def _numpy_dtype_to_hapi_type(dtype: np.dtype) -> str:
    if  np.issubdtype(dtype, np.integer):
        return "int"
    elif np.issubdtype(dtype, np.floating):
        return "double"
    else:
        raise ValueError(f"Unsupported data type {dtype}")


def _create_meta(variable:SpeasyVariable) -> Dict[str, Any]:
    meta = {
        "name": variable.name,
        "units": variable.unit,
        "fill": variable.fill_value,
        "description": variable.meta.get("description", "")
    }
    meta["type"] = _numpy_dtype_to_hapi_type(variable.values.dtype)

    labels  =  variable.columns
    if labels is not None and len(labels) > 0:
        meta["label"] = labels

    if "coordinateSystemName" in variable.meta:
        meta["coordinateSystemName"] = variable.meta["coordinateSystemName"]
    if "vectorComponents" in variable.meta:
        meta["vectorComponents"] = variable.meta["vectorComponents"]

    if  len(variable.values.shape) > 1:
        meta["size"] = variable.values.shape[1:]

    bins = []
    time_independent_axes = _get_variable_axes(variable, is_time_dependent=False)
    if time_independent_axes:
        bins.extend([
            {"name": ax.name, "units": ax.unit, "centers": ax.values.tolist()}
            for ax in time_independent_axes
        ])

    time_dependent_axes = _get_variable_axes(variable, is_time_dependent=True)
    if time_dependent_axes:
        bins.extend([
            {"name": ax.name, "units": ax.unit, "centers": _time_dependent_axis_name(ax)}
            for ax in time_dependent_axes
        ])

    if bins:
        meta["bins"] = bins

    return meta

def _get_hapi_varying_axes(variable: SpeasyVariable) -> List[HapiParameter]:
    result = []
    for ax in _get_variable_axes(variable, is_time_dependent=True):
        # VariableTimeAxis has member 'unit' not 'units'
        # but HapiParameter expects 'units' in meta
        meta = {
            "name": _time_dependent_axis_name(ax),
            "units": ax.unit,
            "size": [ax.values.shape[1]]
        }
        meta["type"] = _numpy_dtype_to_hapi_type(ax.values.dtype)
        result.append(HapiParameter(values=ax.values, meta=meta))
    return result


def _speasy_variables_to_hapi(variables: List[SpeasyVariable]) -> HapiFile:
    if not same_time_axis(variables):
        raise ValueError("All variables must have the same time axis")
    if len(variables) == 0:
        raise ValueError("No variables to save")
    hapi_file = HapiFile()
    hapi_file.add_parameter(_make_hapi_time_axis(variables[0].axes[0]))
    for spz_var in variables:
        # add spz_var as hapi_param
        hapi_file.add_parameter(_make_hapi_parameter(spz_var))
        # add spz_var.axes as hapi_param if time_varying axis
        for hapi_axis_parameter in _get_hapi_varying_axes(spz_var):
            hapi_file.add_parameter(hapi_axis_parameter) 
    return hapi_file

def _bin_to_axis(json_bin: Dict[str, Any], hap_file: HapiFile) -> VariableAxis:
    centers = json_bin.get("centers")
    name = json_bin.get("name", "bin_axis")
    if centers is None:
        raise ValueError("Invalid bin specification: missing 'centers' field")
    if isinstance(centers, str):
        hapi_parameter = hap_file.get_parameter(centers)
        if hapi_parameter is None:
            raise ValueError(f"Unknown parameter referenced in bins: {centers}")
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


def _bins_to_axes(json_bins: List[Dict[str, Any]], hap_file: HapiFile) -> List[VariableAxis]:
    axes = []
    for json_bin in json_bins:
        try:
            axis = _bin_to_axis(json_bin, hap_file)
            axes.append(axis)
        except ValueError as e:
            log.warning(f"Skipping invalid bin specification: {e}")
    return axes

def _hapifile_to_speasy_variables(hapi_file: HapiFile, variables: List[str]) -> Mapping[str, SpeasyVariable]:
    time_axis = VariableTimeAxis(values=hapi_file.time_axis, meta=hapi_file.time_axis_meta)
    loaded_vars = {}
    for var_name in variables:
        parameter = hapi_file.get_parameter(var_name)
        if parameter is None:
            continue
        _axes: List[VariableAxis] = [time_axis]
        if 'bins' in parameter.meta.keys():
            _axes.extend(_bins_to_axes(parameter.meta.get("bins", []), hapi_file))
        loaded_vars[var_name] = SpeasyVariable(axes=_axes, values=DataContainer(parameter.values,
                                                                                name=parameter.name,
                                                                                meta=_decode_meta(
                                                                                parameter.meta)))
    return loaded_vars


class HapiBaseCodec(CodecInterface):

    def __init__(self, loader, saver):
        self._loader = loader
        self._saver = saver

    def load_variables(self, variables, file, cache_remote_files=True, **kwargs):
        hapi_file = self._loader(file)
        if hapi_file is not None:
            return _hapifile_to_speasy_variables(hapi_file, variables)
        return None

    @CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
    def load_variable(self, variable, file, cache_remote_files=True, **kwargs):
        return self.load_variables([variable], file, cache_remote_files)[variable]

    def save_variables(self, variables, file=None, **kwargs):
        hapi_file = _speasy_variables_to_hapi(variables)
        return self._saver(hapi_file, file, **kwargs)

    @property
    def supported_extensions(self):
        return []

    @property
    def supported_mimetypes(self):
        return []
