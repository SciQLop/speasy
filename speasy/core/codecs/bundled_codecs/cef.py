"""CEF (Cluster Exchange Format) codec, read with CEFast.

Format: ESA DS-QMW-TN-0010 "CEF: Cluster Exchange Format", version 2.0, with the attributes of the CAA/CSA
metadata dictionary (https://www.cosmos.esa.int/web/csa/documentation).
"""
import io
from typing import AnyStr, List, Mapping, Optional, Union

import cefast
import numpy as np

from speasy.core.codecs import Buffer, CodecInterface, register_codec
from speasy.products import DataContainer, SpeasyVariable, VariableAxis, VariableTimeAxis

from .istp import _resolve_url_type

# The CEF spelling of attributes that speasy, its plots and SciQLop read under their ISTP names.
_ISTP_NAMES = {
    "DISPLAYTYPE": ("DISPLAY_TYPE", lambda value: value),
    "SI_CONVERSION": ("SI_conversion", lambda value: value),
    "PARAMETER_TYPE": ("VAR_TYPE", str.lower),  # CEF writes Data / Support_Data, ISTP data / support_data
}
_TIMES = ("ISO_TIME", "ISO_TIME_RANGE")
_NOT_AN_AXIS = ("CHAR",) + _TIMES


def _load_file(file: Union[Buffer, str, io.IOBase], cache_remote_files: bool) -> Optional[cefast.CEF]:
    kind, content = _resolve_url_type(file, cache_remote_files=cache_remote_files)
    if content is None:
        return None
    try:
        return cefast.load(content)
    except cefast.ParseError as e:
        where = content if kind == "file" else "the given content"
        raise ValueError(f"Can't read {where} as a CEF 2.0 file: {e}") from e


def _meta(variable: cefast.Variable) -> dict:
    attributes = variable.attributes
    return {**attributes, **{istp: convert(attributes[cef]) for cef, (istp, convert) in _ISTP_NAMES.items()
                             if cef in attributes}}


def _record_times(time_variable: cefast.Variable) -> np.ndarray:
    times = time_variable.values
    if time_variable.value_type == "ISO_TIME_RANGE":
        # a record spanning an interval is placed at its middle, as a time tag with equal DELTA_MINUS and DELTA_PLUS
        return times[:, 0] + (times[:, 1] - times[:, 0]) / 2
    return times


def _names(cef: cefast.CEF, value) -> Optional[list]:
    """LABEL_i and REPRESENTATION_i give the names themselves, or the name of a fixed variable holding them."""
    if isinstance(value, str) and value in cef and cef[value].is_nrv:
        return cef[value].values.tolist()
    if value is None or isinstance(value, list):
        return value
    return [value]


def _columns(cef: cefast.CEF, variable: cefast.Variable, values: np.ndarray) -> List[str]:
    if values.ndim != 2:
        return [str(variable.attributes.get("LABLAXIS", variable.name))]
    width = values.shape[1]
    candidates = (_names(cef, variable.attributes.get(key)) for key in ("LABEL_1", "REPRESENTATION_1"))
    return next(([str(name) for name in names] for names in candidates if names is not None and len(names) == width),
                [f"component_{i}" for i in range(width)])


def _depends(variable: cefast.Variable, ndim: int) -> List[Optional[str]]:
    """DEPEND_1 … up to the last one given: axes are positional, so a gap before a later DEPEND still needs one."""
    depends = [variable.attributes.get(f"DEPEND_{dim}") for dim in range(1, ndim)]
    given = [dim for dim, depend in enumerate(depends) if depend is not None]
    return depends[:given[-1] + 1] if given else []


def _axis(cef: cefast.CEF, depend: Optional[str], owner: str, dim: int, size: int, keep: np.ndarray) -> VariableAxis:
    if depend is not None and depend in cef and cef[depend].value_type not in _NOT_AN_AXIS:
        support = cef[depend]
        return VariableAxis(values=support.values if support.is_nrv else support.values[keep], meta=_meta(support),
                            name=depend, is_time_dependent=not support.is_nrv)
    return VariableAxis(values=np.arange(size), name=f"{owner}_index_{dim}")


def _time_series(cef: cefast.CEF, name: AnyStr) -> Optional[SpeasyVariable]:
    variable = cef.get(name)
    time_name = variable.attributes.get("DEPEND_0") if variable is not None else None
    if time_name is None or time_name not in cef or variable.is_nrv or cef[time_name].value_type not in _TIMES:
        return None
    times = _record_times(cef[time_name])
    keep = ~np.isnat(times)
    if not keep.any():
        return None
    values = variable.values[keep]
    extra_axes = [_axis(cef, depend, name, dim, values.shape[dim], keep)
                  for dim, depend in enumerate(_depends(variable, values.ndim), start=1)]
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=times[keep], meta=cef[time_name].attributes)] + extra_axes,
        values=DataContainer(values=values, meta=_meta(variable), name=name, is_time_dependent=True),
        columns=_columns(cef, variable, values))


@register_codec
class Cef(CodecInterface):
    """Read-only codec for CEF 2.0 files, the text format of the Cluster Science Archive. Uses CEFast."""

    def load_variables(self, variables: List[AnyStr], file: Union[Buffer, str, io.IOBase], cache_remote_files=True,
                       **kwargs) -> Optional[Mapping[AnyStr, Optional[SpeasyVariable]]]:
        cef = _load_file(file, cache_remote_files)
        if cef is None:
            return None
        return {name: _time_series(cef, name) for name in variables}

    def load_variable(self, variable: AnyStr, file: Union[Buffer, str, io.IOBase], cache_remote_files=True,
                      **kwargs) -> Optional[SpeasyVariable]:
        loaded = self.load_variables([variable], file, cache_remote_files)
        return loaded[variable] if loaded is not None else None

    def list_variables(self, file: Union[Buffer, str, io.IOBase]) -> List[str]:
        cef = _load_file(file, cache_remote_files=True)
        return [name for name, variable in cef.items() if "DEPEND_0" in variable.attributes and not variable.is_nrv]

    def save_variables(self, variables: List[SpeasyVariable], file: Optional[Union[str, io.IOBase]] = None,
                       **kwargs) -> Union[bool, Buffer]:
        raise NotImplementedError("Speasy reads CEF files but can't write them")

    @property
    def supported_extensions(self) -> List[str]:
        return ["cef"]

    @property
    def supported_mimetypes(self) -> List[str]:
        return ["application/x-cef"]

    @property
    def name(self) -> str:
        return self.__class__.__name__
