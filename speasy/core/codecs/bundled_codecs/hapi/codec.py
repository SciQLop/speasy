from datetime import timedelta

import numpy as np

from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from speasy.core.cache._function_cache import CacheCall
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products.variable import SpeasyVariable, same_time_axis

from .hapi_file import HapiFile, HapiParameter
from .isotime import isotime_length, isotime_unit

import logging
log = logging.getLogger(__name__)

def _time_dependent_axis_name(ax: VariableAxis) -> str:
    return f"{ax.name}_centers_time_varying"

def _get_variable_axes(variable: SpeasyVariable, is_time_dependent: bool) -> List[VariableAxis]:
    return [ax for ax in variable.axes[1:] if ax.is_time_dependent == is_time_dependent]

# HAPI always spells fill as a string, whatever the parameter's type, while masking compares it
# against the data, so it has to be read back in the data's own type.
_fill_value_parsers = {"double": float, "integer": int}


def _decode_fill_value(fill: Any, hapi_type: str) -> Any:
    parser = _fill_value_parsers.get(hapi_type)
    if parser is None or not isinstance(fill, str):
        return fill
    try:
        return parser(fill)
    except ValueError:
        log.warning(f"Ignoring fill value {fill!r}, which is not a valid {hapi_type}")
        return None


def _decode_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    if "units" in meta:
        meta["UNITS"] = meta.pop("units")
    fill = _decode_fill_value(meta.pop("fill", None), meta.get("type", ""))
    if fill is not None:
        meta["FILLVAL"] = fill
    return meta

def _hapi_size(shape: Tuple[int, ...]) -> List[int]:
    # A single column is a HAPI scalar: "size": [1] is discouraged as ambiguous.
    size = list(shape)
    return [] if size == [1] else size


def _is_blank(text: Any) -> bool:
    return not isinstance(text, str) or not text.strip()


def _parameter_units(unit: Any, size: List[int]) -> Union[None, str, List[Optional[str]]]:
    # HAPI spells "no units" as null and never as an empty string; ISTP UNITS can also be one per element,
    # which HAPI only allows as an array matching a 1-D size.
    if isinstance(unit, (list, tuple, np.ndarray)):
        units = [None if _is_blank(u) else u for u in np.ravel(unit).tolist()]
        if len(set(units)) == 1:
            return units[0]
        if len(size) == 1 and len(units) == size[0]:
            return units
        return None
    return None if _is_blank(unit) else unit


def _bin_units(unit: Any) -> str:
    # Unlike parameters, bins must name a single unit, null isn't allowed.
    return _parameter_units(unit, []) or "dimensionless"


def _vector_components(components: Any, size: List[int]) -> Union[None, str, List[str]]:
    # A scalar takes one string, a 1-D array one per element; HAPI has none for other shapes.
    if components is None:
        return None
    components = [components] if isinstance(components, str) else np.ravel(components).tolist()
    if any(_is_blank(c) for c in components):
        return None
    if not size and len(components) == 1:
        return components[0]
    if len(size) == 1 and len(components) == size[0]:
        return components
    return None


def _make_hapi_time_axis(time_axis: VariableTimeAxis) -> HapiParameter:
    length = isotime_length(isotime_unit(time_axis.values))
    return HapiParameter(values=time_axis.values,
                            meta={"name": "Time", "type": "isotime", "units": "UTC", "length": length, "fill": None})

def _make_hapi_parameter(variable: SpeasyVariable) -> HapiParameter:
    return HapiParameter(values=variable.values,
                            meta=_create_meta(variable))

_INT32 = np.iinfo(np.int32)


def _hapi_type(values: np.ndarray) -> str:
    # HAPI integers are 32-bit: wider integers that don't fit go out as doubles rather than wrap around.
    if np.issubdtype(values.dtype, np.integer):
        if np.can_cast(values.dtype, np.int32) or values.size == 0 or (
                _INT32.min <= values.min() and values.max() <= _INT32.max):
            return "integer"
        return "double"
    elif np.issubdtype(values.dtype, np.floating):
        return "double"
    else:
        raise ValueError(f"Unsupported data type {values.dtype}")


def _encode_fill_value(fill: Any, hapi_type: str) -> Optional[str]:
    # HAPI wants a single value spelled as a string; ISTP FILLVALs often come as a one-element array.
    if isinstance(fill, (list, tuple, np.ndarray)):
        fill = np.ravel(fill)
        if len(fill) != 1:
            return None
        fill = fill[0]
    if fill is None:
        return None
    try:
        fill = float(fill)
    except (TypeError, ValueError, OverflowError):
        log.warning(f"Ignoring fill value {fill!r}, which is not a number a double can hold")
        return None
    if np.isnan(fill):
        return "NaN" if hapi_type == "double" else None
    if hapi_type == "integer":
        if fill.is_integer() and _INT32.min <= fill <= _INT32.max:
            return str(int(fill))
        return None
    return repr(fill)


def _create_meta(variable:SpeasyVariable) -> Dict[str, Any]:
    hapi_type = _hapi_type(variable.values)
    size = _hapi_size(variable.values.shape[1:])
    meta = {
        "name": variable.name,
        "units": _parameter_units(variable.unit, size),
        "fill": _encode_fill_value(variable.fill_value, hapi_type),
        "description": variable.meta.get("description", "")
    }
    meta["type"] = hapi_type

    if size:
        meta["size"] = size

    labels = variable.columns
    # HAPI labels are non-empty strings, one per element of a 1-D array or a single one for a scalar.
    if labels and all(isinstance(lbl, str) and lbl.strip() for lbl in labels):
        if not size and len(labels) == 1:
            meta["label"] = labels[0]
        elif size == [len(labels)]:
            meta["label"] = labels

    if not _is_blank(variable.meta.get("coordinateSystemName")):
        meta["coordinateSystemName"] = variable.meta["coordinateSystemName"]
    if "vectorComponents" in variable.meta:
        components = _vector_components(variable.meta["vectorComponents"], size)
        if components is not None:
            meta["vectorComponents"] = components

    # bins describe the array's dimensions in order, so they only go out when there is one axis per dimension.
    axes = variable.axes[1:]
    if size and len(axes) == len(size):
        meta["bins"] = [_make_bin(ax, n) for ax, n in zip(axes, size)]

    return meta

def _make_bin(ax: VariableAxis, n: int) -> Dict[str, Any]:
    # HAPI centers give one number per element of this dimension only, constant or per record, and
    # constant ones can't be missing. Anything else, such as ISTP vector components labelled "x_component"
    # or a latitude grid spanning several dimensions, marks the dimension as not binned with null centers.
    numeric = np.issubdtype(ax.values.dtype, np.number)
    if ax.is_time_dependent and numeric and ax.values.shape[1:] == (n,):
        centers = _time_dependent_axis_name(ax)
    elif not ax.is_time_dependent and numeric and ax.values.shape == (n,) and np.all(np.isfinite(ax.values)):
        centers = ax.values.tolist()
    else:
        centers = None
    return {"name": ax.name, "units": _bin_units(ax.unit), "centers": centers}


def _get_hapi_varying_axes(variable: SpeasyVariable) -> List[HapiParameter]:
    result = []
    for ax in _get_variable_axes(variable, is_time_dependent=True):
        # VariableTimeAxis has member 'unit' not 'units'
        # but HapiParameter expects 'units' in meta
        size = _hapi_size(ax.values.shape[1:])
        meta = {
            "name": _time_dependent_axis_name(ax),
            "units": _parameter_units(ax.unit, size),
            "fill": None,
        }
        meta["type"] = _hapi_type(ax.values)
        if meta["type"] == "double" and np.isnan(ax.values).any():
            meta["fill"] = "NaN"
        if size:
            meta["size"] = size
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

def _ranges_to_axis(ranges: Any, name: str, units: Any, hap_file: HapiFile) -> VariableAxis:
    # Bins given only by their [min, max] ranges are centered on the middle of each range.
    if isinstance(ranges, str):
        hapi_parameter = hap_file.get_parameter(ranges)
        if hapi_parameter is None:
            raise ValueError(f"Unknown parameter referenced in bins: {ranges}")
        return VariableAxis(values=hapi_parameter.values.mean(axis=-1), meta=_decode_meta(dict(hapi_parameter.meta)),
                            is_time_dependent=True, name=name)
    try:
        bounds = np.array(ranges, dtype=float)
    except ValueError:
        raise ValueError("Invalid bin specification: 'ranges' must contain numeric [min, max] pairs")
    if bounds.ndim != 2 or bounds.shape[1] != 2:
        raise ValueError("Invalid bin specification: 'ranges' must contain numeric [min, max] pairs")
    return VariableAxis(values=bounds.mean(axis=1), meta={"name": "centers", "UNITS": units},
                        is_time_dependent=False, name=name)


def _bin_to_axis(json_bin: Dict[str, Any], hap_file: HapiFile) -> VariableAxis:
    centers = json_bin.get("centers")
    name = json_bin.get("name", "bin_axis")
    if centers is None and json_bin.get("ranges") is not None:
        return _ranges_to_axis(json_bin["ranges"], name, json_bin.get("units"), hap_file)
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


def _index_axis(json_bin: Dict[str, Any], n: int) -> VariableAxis:
    # keeps the following axes on their own dimension when this one has no usable centers
    return VariableAxis(values=np.arange(n, dtype=float), meta={"name": "index", "UNITS": None},
                        is_time_dependent=False, name=json_bin.get("name", "bin_axis"))


def _bins_to_axes(json_bins: List[Dict[str, Any]], hap_file: HapiFile,
                  size: Optional[List[int]] = None) -> List[VariableAxis]:
    # With one bin per dimension of size, a bin without usable centers becomes an index axis so the
    # following ones stay on their own dimension; otherwise such bins can only be skipped.
    sizes = size if size is not None and len(size) == len(json_bins) else [None] * len(json_bins)
    axes = []
    for json_bin, n in zip(json_bins, sizes):
        try:
            if "centers" in json_bin and json_bin["centers"] is None and "ranges" not in json_bin:
                if n is not None:
                    axes.append(_index_axis(json_bin, n))  # a dimension that isn't binned
                continue
            axes.append(_bin_to_axis(json_bin, hap_file))
        except ValueError as e:
            log.warning(f"Skipping invalid bin specification: {e}")
            if n is not None:
                axes.append(_index_axis(json_bin, n))
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
            _axes.extend(_bins_to_axes(parameter.meta.get("bins", []), hapi_file, parameter.meta.get("size", [])))
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
