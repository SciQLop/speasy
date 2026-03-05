from typing import List, AnyStr, Optional, Mapping, Union, Dict, Any
import io
import logging

from datetime import timedelta
import numpy as np

from speasy.core.codecs import CodecInterface, register_codec
from speasy.core.codecs.codec_interface import Buffer
from speasy.core.cache import CacheCall
from speasy.core.data_containers import VariableAxis
from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer
from speasy.products.variable import same_time_axis
from .csv_file import HapiCsvFile, HapiCsvParameter

log = logging.getLogger(__name__)
from .reader import load_hapi_csv
from .writer import save_hapi_csv


def _create_meta(variable:SpeasyVariable) -> Dict[str, Any]:
    meta = {
        "name": variable.name,
        "units": variable.unit,
        "fill": variable.fill_value,
        "description": variable.meta.get("description", "")
    }
    if  np.issubdtype(variable.values.dtype, np.integer):
        meta["type"] = "int"
    elif np.issubdtype(variable.values.dtype, np.floating):
        meta["type"] = "double"
    else:
        raise ValueError(f"Unsupported data type {variable.values.dtype}")

    labels  =  variable.columns
    if labels is not None and len(labels) > 0:
        meta["label"] = labels

    if "coordinateSystemName" in variable.meta:
        meta["coordinateSystemName"] = variable.meta["coordinateSystemName"]
    if "vectorComponents" in variable.meta:
        meta["vectorComponents"] = variable.meta["vectorComponents"]

    if  len(variable.values.shape) > 1:
        meta["size"] = variable.values.shape[1:]
    return meta


def _decode_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    if "units" in meta:
        meta["UNITS"] = meta.pop("units")
    return meta


def _bin_to_axis(json_bin: Dict[str, Any], hap_csv_file: HapiCsvFile) -> VariableAxis:
    centers = json_bin.get("centers")
    name = json_bin.get("name", "bin_axis")
    if centers is None:
        raise ValueError("Invalid bin specification: missing 'centers' field")
    if isinstance(centers, str):
        hapi_parameter = hap_csv_file.get_parameter(centers)
        variable_axis = VariableAxis(values=hapi_parameter.values,
                                     meta=hapi_parameter.meta,
                                     is_time_dependent=True,
                                     name=name)
    elif isinstance(centers, list):
        try:
            axis_values = np.array(centers, dtype=float)
        except ValueError:
            raise ValueError("Invalid bin specification: 'centers' list must contain numeric values")
        variable_axis = VariableAxis(values=axis_values,
                                     meta={"name": "centers"},
                                     is_time_dependent=False,
                                     name=name)
    else:
        raise ValueError("Invalid bin specification: 'centers' must be either a string or a list")
    return variable_axis


def _bins_to_axes(json_bins: List[Dict[str, Any]], hap_csv_file: HapiCsvFile) -> List[VariableAxis]:
    axes = []
    for json_bin in json_bins:
        try:
            axis = _bin_to_axis(json_bin, hap_csv_file)
            axes.append(axis)
        except ValueError as e:
            log.warning(f"Skipping invalid bin specification: {e}")
    return axes


def _hapi_csv_to_speasy_variables(hapi_csv_file: HapiCsvFile, variables: List[AnyStr]) -> Mapping[str, SpeasyVariable]:
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


def _make_hapi_csv_parameter(variable: SpeasyVariable) -> HapiCsvParameter:
    return HapiCsvParameter(values=variable.values,
                            meta=_create_meta(variable))


def _make_hapi_csv_time_axis(time_axis: VariableTimeAxis) -> HapiCsvParameter:
    return HapiCsvParameter(values=time_axis.values,
                            meta={"name": "Time", "type": "isotime", "units": "UTC", "length": 30, "fill": None})


def _speasy_variables_to_hapi_csv(variables: List[SpeasyVariable]) -> HapiCsvFile:
    if not same_time_axis(variables):
        raise ValueError("All variables must have the same time axis")
    if len(variables) == 0:
        raise ValueError("No variables to save")
    hapi_csv_file = HapiCsvFile()
    hapi_csv_file.add_parameter(_make_hapi_csv_time_axis(variables[0].axes[0]))
    for var in variables:
        hapi_csv_file.add_parameter(_make_hapi_csv_parameter(var))
    return hapi_csv_file


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
        hapi_csv_file = _speasy_variables_to_hapi_csv(variables)
        return save_hapi_csv(hapi_csv_file, file)

    @property
    def supported_extensions(self) -> List[str]:
        return []

    @property
    def supported_mimetypes(self) -> List[str]:
        return []

    @property
    def name(self) -> str:
        return "hapi/csv"
