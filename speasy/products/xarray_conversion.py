"""Conversion between SpeasyVariable and xarray objects.

xarray is an optional dependency. Importing from xarray objects never imports it; exporting does.
"""
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pds

from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis

if TYPE_CHECKING:
    from .variable import SpeasyVariable

ISTP_TO_CF = {
    "UNITS": "units",
    "FILLVAL": "_FillValue",
    "VALIDMIN": "valid_min",
    "VALIDMAX": "valid_max",
}
CF_TO_ISTP = {cf: istp for istp, cf in ISTP_TO_CF.items()}
COLUMNS = "columns"
PREFERRED_TIME_NAMES = ("time", "epoch")


def _xarray():
    try:
        import xarray
    except ImportError as e:
        raise ImportError("Converting to xarray needs the xarray package, install it with: "
                          "pip install speasy[xarray]") from e
    return xarray


def _renamed_keys(meta: Dict, mapping: Dict[str, str]) -> Dict:
    """Renames keys following mapping, unless the target name is already taken."""
    return {(mapping[k] if k in mapping and mapping[k] not in meta else k): v for k, v in meta.items()}


def _to_attrs(meta: Dict) -> Dict:
    return _renamed_keys(meta, ISTP_TO_CF)


def _to_meta(attrs: Dict) -> Dict:
    meta = _renamed_keys(attrs, CF_TO_ISTP)
    if "UNITS" in meta and not isinstance(meta["UNITS"], str):
        # some producers (maser-data) store astropy Unit objects
        meta["UNITS"] = str(meta["UNITS"])
    return meta


def _is_sweep(var: "SpeasyVariable") -> bool:
    """1D data whose extra axes only follow time, like a radio receiver sweeping frequencies."""
    return var.values.shape[1:] == (1,) and all(ax.values.shape == (len(var),) for ax in var.axes[1:])


def _columns_label_dim_1(var: "SpeasyVariable") -> bool:
    return var.values.ndim >= 2 and len(var.columns) == var.values.shape[1]


def _dim_name(var: "SpeasyVariable", index: int) -> str:
    if index < len(var.axes) and var.axes[index].name:
        return var.axes[index].name
    if index == 1 and _columns_label_dim_1(var):
        return COLUMNS
    return f"dim_{index}"


def _axis_dims(axis, index: int, dims: List[str], shape) -> tuple:
    if axis.values.shape == shape:
        return tuple(dims)
    if axis.values.shape == shape[1:]:
        return tuple(dims[1:])
    if axis.is_time_dependent and axis.values.ndim == 1:
        return (dims[0],)
    if axis.is_time_dependent:
        return dims[0], dims[index]
    return (dims[index],)


def _columns_coord(var: "SpeasyVariable", dims: List[str]) -> Dict[str, Any]:
    """Columns label dim 1 when they match it, a single label (MMS HPCA's 'H+ Flux') is kept as a scalar."""
    if len(dims) > 1 and _columns_label_dim_1(var):
        return {COLUMNS: (dims[1], var.columns)}
    if len(var.columns) == 1:
        return {COLUMNS: ((), var.columns[0])}
    return {}


def to_dataarray(var: "SpeasyVariable"):
    xr = _xarray()
    values = var.values[:, 0] if _is_sweep(var) else var.values
    dims = [var.axes[0].name or "time"] + [_dim_name(var, i) for i in range(1, values.ndim)]
    coords = {dims[0]: (dims[0], var.time, _to_attrs(var.axes[0].meta))}
    coords.update({
        axis.name or dims[index]: (_axis_dims(axis, index, dims, values.shape), axis.values, _to_attrs(axis.meta))
        for index, axis in enumerate(var.axes[1:], start=1)
    })
    coords.update(_columns_coord(var, dims))
    return xr.DataArray(values, dims=dims, coords=coords, name=var.name, attrs=_to_attrs(var.meta))


def _time_dims(da) -> List[str]:
    return [d for d in da.dims if isinstance(da.indexes.get(d), pds.DatetimeIndex)]


def _find_time_dim(da, time_dim: Optional[str]) -> Optional[str]:
    if time_dim is not None:
        return time_dim if time_dim in _time_dims(da) else None
    candidates = _time_dims(da)
    preferred = [d for d in candidates if str(d).lower() in PREFERRED_TIME_NAMES]
    if len(candidates) == 1:
        return candidates[0]
    if len(preferred) == 1:
        return preferred[0]
    if candidates:
        raise ValueError(f"Several time dimensions in {da.name}: {candidates}, pick one with time_dim=")
    return None


def _time_axis(da, time_dim: str) -> VariableTimeAxis:
    index = da.indexes[time_dim]
    if index.tz is not None:
        index = index.tz_convert(None)
    return VariableTimeAxis(values=index.values.astype("datetime64[ns]"), name=str(time_dim),
                            meta=_to_meta(da[time_dim].attrs))


def _is_labels_dim(da, dim: str) -> bool:
    """The second dim of a 2D array indexed by strings, like vector components, when no columns coordinate exists."""
    return COLUMNS not in da.coords and da.ndim == 2 and dim in da.indexes and da.indexes[dim].dtype.kind in "OUS"


def _columns(da) -> Optional[List[str]]:
    if COLUMNS in da.coords and da[COLUMNS].dims in ((), da.dims[1:2]):
        return [str(label) for label in np.atleast_1d(da[COLUMNS].values)]
    if _is_labels_dim(da, da.dims[-1]):
        return [str(label) for label in da.indexes[da.dims[-1]]]
    return None


def _make_axis(coord, is_time_dependent: bool) -> VariableAxis:
    return VariableAxis(values=coord.values, name=str(coord.name), meta=_to_meta(coord.attrs),
                        is_time_dependent=is_time_dependent)


def _axis(da, dim: str) -> Optional[VariableAxis]:
    """The coordinate describing dim: one following time and dim, or named after dim and spanning
    every dim (PSP EPI-Lo energies), the spatial dims (GOLD latitude/longitude grids) or dim alone."""
    # da.coords.get would invent an index coordinate for dims without one
    named = da.coords[dim] if dim in da.coords and dim != COLUMNS else None
    time_varying = [c for c in da.coords if c != COLUMNS and da[c].dims == (da.dims[0], dim)]
    if named is not None and named.dims == da.dims:
        return _make_axis(named, is_time_dependent=True)
    if time_varying:
        return _make_axis(da[time_varying[0]], is_time_dependent=True)
    if named is not None and named.dims in ((dim,), da.dims[1:]) and not _is_labels_dim(da, dim):
        return _make_axis(named, is_time_dependent=False)
    return None


def _sweep_axis(da) -> Optional[VariableAxis]:
    """The single numeric coordinate following time of 1D data, see _is_sweep."""
    candidates = [c for c in da.coords
                  if c not in (da.dims[0], COLUMNS) and da[c].dims == da.dims and da[c].dtype.kind in "iuf"]
    if len(candidates) == 1:
        return _make_axis(da[candidates[0]], is_time_dependent=True)
    return None


def _extra_axes(da) -> List[VariableAxis]:
    if da.ndim == 1:
        axis = _sweep_axis(da)
        return [axis] if axis is not None else []
    axes = [_axis(da, dim) for dim in da.dims[1:]]
    while axes and axes[-1] is None:
        axes.pop()
    # Speasy axes are positional, a dim without coordinate before a labelled one still needs an axis
    return [axis if axis is not None else VariableAxis(values=np.arange(da.sizes[dim]), name=str(dim))
            for axis, dim in zip(axes, da.dims[1:])]


def has_time_dim(da, time_dim: Optional[str] = None) -> bool:
    return _find_time_dim(da, time_dim) is not None


def variable_parts(da, time_dim: Optional[str] = None) -> Tuple[List, DataContainer, Optional[List[str]]]:
    """The axes, values and columns of the SpeasyVariable matching da.

    Returned as parts rather than a SpeasyVariable so this module does not import products, which import it.
    """
    found = _find_time_dim(da, time_dim)
    if found is None:
        raise ValueError(f"No datetime dimension found in {da.name} (dims: {list(da.dims)}), "
                         f"give its name with time_dim=")
    da = da.transpose(found, ...)
    values = DataContainer(values=da.values, meta=_to_meta(da.attrs),
                           name=str(da.name) if da.name is not None else "Unknown")
    return [_time_axis(da, found), *_extra_axes(da)], values, _columns(da)
