"""What numpy can't do along a SpeasyVariable axis: find it by name, select by value, integrate with bin widths::

    d = dist.replace_fillval_by_nan()
    spectrum = np.nansum(sel(d, "energy", [1e3, 1e4]), axis=dimension(d, "phi"))
    density = integrate(np.nanmean(d, axis=(dimension(d, "phi"), dimension(d, "theta"))), "energy")

Sums, means and positional selection are numpy's: ``np.nansum``, ``np.nanmean``, ``np.average`` and ``var[:, :, 3]``.

An axis is given by its exact name, by a part of its name matching a single axis (ignoring case), or by its dimension
in ``var.values`` (1 is the first axis after time). Time is not an axis here: the requested range, or
``var[start:stop]``, selects it. Edges are lists, arrays or SpeasyVariables. Bin widths for ``integrate`` come from
``edges``, else from the axis' ISTP DELTA_PLUS_VAR / DELTA_MINUS_VAR, else from the midpoints between sorted values;
otherwise it is an error.
"""
import re
from typing import List, Optional

import numpy as np

from speasy.core.data_containers import DataContainer, VariableAxis, fill_value_mask

__all__ = ['dimension', 'sel', 'integrate', 'bin_widths']

Axis = int | str


def _axes_list(var) -> str:
    return ', '.join(f"{axis.name!r} ({i})" for i, axis in enumerate(var.axes[1:], 1))


def _named(var, name: str) -> int:
    """The axis named exactly ``name``, else the only non-time axis whose name contains it, ignoring case."""
    exact = [i for i, axis in enumerate(var.axes) if axis.name == name]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"Several axes are named {name!r}: give its dimension instead, one of {_axes_list(var)}")
    found = [i for i, axis in enumerate(var.axes[1:], 1) if name.lower() in axis.name.lower()]
    if not found:
        raise ValueError(f"No axis {name!r}: give one of {_axes_list(var)}, by name, part of a name, or dimension")
    if len(found) > 1:
        matches = ', '.join(f"{var.axes[i].name!r} ({i})" for i in found)
        raise ValueError(f"{name!r} matches several axes, {matches}: give more of the name, or the dimension")
    return found[0]


def _array(given) -> np.ndarray:
    """``given`` (a list, an array or a SpeasyVariable) as a float array; a single record of a variable counts as
    one value per bin."""
    array = np.asarray(getattr(given, 'values', given), dtype=float)
    return array[0] if array.ndim == 2 and array.shape[0] == 1 else array


def dimension(var, axis: Axis) -> int:
    """The dimension of ``axis`` in ``var.values``, for numpy's ``axis=``: ``axis`` is an exact axis name, a part of a
    name matching a single axis (ignoring case), or a dimension (negative counts from the end). Time is refused."""
    index = _named(var, axis) if isinstance(axis, str) else int(axis)
    if -len(var.axes) < index < 0:
        index += len(var.axes)
    if index == 0:
        raise ValueError("The time axis is not one to reduce: select time with the requested range, or v[start:stop]")
    if not 0 < index < len(var.axes):
        raise ValueError(f"No axis {axis!r}: give one of {_axes_list(var)}, by name or dimension")
    return index


def _reducible(var, axis: Axis) -> int:
    index = dimension(var, axis)
    values = var.axes[index].values
    if values.ndim != (2 if var.axes[index].is_time_dependent else 1):
        raise ValueError(f"Axis {var.axes[index].name!r} spans several dimensions of the data (shape {values.shape}): "
                         f"reducing it is not supported")
    return index


def _along(array: np.ndarray, index: int, ndim: int) -> np.ndarray:
    """An array shaped like an axis' values ((n,) or (records, n)), ready to broadcast along dimension ``index``."""
    shape = [1] * ndim
    shape[index] = array.shape[-1]
    if array.ndim == 2:
        shape[0] = array.shape[0]
    return array.reshape(shape)


def _float_values(var) -> np.ndarray:
    values = np.array(var.values, dtype=float)
    mask = fill_value_mask(var.values, var.meta)
    if mask is not None:
        values[mask] = np.nan
    return values


def _rebuilt(var, values: np.ndarray, axes: List, unit: Optional[str] = None):
    from speasy.products.variable import SpeasyVariable
    meta = {k: v for k, v in var.meta.items() if not re.fullmatch(r'(DEPEND|LABL_PTR)_[1-9]', k)}
    meta.update({f'DEPEND_{i}': axis.name for i, axis in enumerate(axes[1:], 1)})
    if unit is not None:
        meta['UNITS'] = unit
    same_columns = len(axes) == 2 and len(var.axes) > 1 and axes[1] is var.axes[1] and values.ndim == 2 and \
        len(var.columns) == values.shape[1]
    return SpeasyVariable(axes=axes, values=DataContainer(values=values, meta=meta, name=var.name),
                          columns=var.columns if same_columns else None)


def _dropped(var, index: int, values: np.ndarray, unit: Optional[str] = None):
    return _rebuilt(var, values, [axis for i, axis in enumerate(var.axes) if i != index], unit)


def _weighted_sum(var, index: int, weights: np.ndarray):
    """Σ w·x over the valid values along ``index``, and Σ w over the same values."""
    values = _float_values(var)
    valid = np.isfinite(values)
    weights = np.broadcast_to(_along(weights, index, values.ndim), values.shape)
    return np.sum(np.where(valid, values * weights, 0.), axis=index), np.sum(np.where(valid, weights, 0.), axis=index)


def _width_error(axis: VariableAxis, why: str) -> ValueError:
    return ValueError(f"Can't tell the bin widths of {axis.name!r}: {why}. Give its bin edges: "
                      f"integrate(..., edges=[...]), one more than its values")


def _widths_from_edges(axis: VariableAxis, edges) -> np.ndarray:
    edges = _array(edges)
    if edges.shape[-1] != axis.values.shape[-1] + 1:
        raise ValueError(f"edges for {axis.name!r} must hold {axis.values.shape[-1] + 1} values, got {edges.shape[-1]}")
    return np.abs(np.diff(edges, axis=-1))


def _widths_from_deltas(axis: VariableAxis) -> np.ndarray:
    widths = axis.delta_plus + axis.delta_minus
    if not np.all(np.isfinite(widths) & (widths > 0)):
        raise _width_error(axis, "its DELTA_PLUS_VAR / DELTA_MINUS_VAR hold missing or non-positive widths")
    return widths


def _widths_from_midpoints(axis: VariableAxis) -> np.ndarray:
    values = np.asarray(axis.values, dtype=float)
    steps = np.diff(values, axis=-1)
    if values.shape[-1] < 2 or not (np.all(steps > 0) or np.all(steps < 0)):
        raise _width_error(axis, "it has no DELTA_PLUS_VAR / DELTA_MINUS_VAR and its values are not sorted")
    half = steps / 2
    edges = np.concatenate([values[..., :1] - half[..., :1], values[..., :-1] + half, values[..., -1:] + half[..., -1:]],
                           axis=-1)
    return np.abs(np.diff(edges, axis=-1))


def bin_widths(axis: VariableAxis, edges=None) -> np.ndarray:
    """Each bin's width, with the shape of the axis values: from ``edges``, else from the axis deltas, else from the
    midpoints between its values."""
    if edges is not None:
        return _widths_from_edges(axis, edges)
    if axis.delta_plus is not None:
        return _widths_from_deltas(axis)
    return _widths_from_midpoints(axis)


def _times_unit(unit: Optional[str], axis_unit: Optional[str]) -> Optional[str]:
    if not axis_unit:
        return unit
    if not unit:
        return axis_unit
    import astropy.units as u
    try:
        return (u.Unit(unit) * u.Unit(axis_unit)).to_string()
    except (ValueError, TypeError):
        return f"({unit}) {axis_unit}"


def integrate(var, axis: Axis, edges=None):
    """Sum along ``axis`` of each value times its bin width (the histogram integral, not a trapezoid rule). The unit is
    multiplied by the axis unit."""
    index = _reducible(var, axis)
    axis_ = var.axes[index]
    sums, counts = _weighted_sum(var, index, bin_widths(axis_, edges))
    return _dropped(var, index, np.where(counts > 0, sums, np.nan), _times_unit(var.unit, axis_.unit))


def _axis_columns(axis: VariableAxis, columns: np.ndarray) -> VariableAxis:
    def pick(a):
        return None if a is None else a[..., columns]
    return VariableAxis(values=axis.values[..., columns], meta=axis.meta, name=axis.name,
                        is_time_dependent=axis.is_time_dependent, delta_plus=pick(axis.delta_plus),
                        delta_minus=pick(axis.delta_minus))


def _take_columns(var, index: int, columns: np.ndarray, values: Optional[np.ndarray] = None):
    values = np.take(var.values if values is None else values, columns, axis=index)
    axes = list(var.axes)
    axes[index] = _axis_columns(var.axes[index], columns)
    return _rebuilt(var, values, axes)


def _as_slice(key):
    if isinstance(key, (list, tuple)) and len(key) != 2:
        raise ValueError(f"a range is [lo, hi], got {key!r}: give both bounds, None for no limit on that side")
    key = slice(*key) if isinstance(key, (list, tuple)) else key
    if isinstance(key, slice) and key.step is not None:
        raise ValueError(f"sel takes no step, got {key!r}: select the range, then index it, e.g. v[:, ::2]")
    return key


def _sel_range(var, index: int, start, stop):
    axis = var.axes[index]
    lo, hi = sorted((-np.inf if start is None else float(start), np.inf if stop is None else float(stop)))
    inside = (axis.values >= lo) & (axis.values <= hi)
    columns = np.flatnonzero(inside if inside.ndim == 1 else inside.any(axis=0))
    if len(columns) == 0:
        raise ValueError(f"No value of {axis.name!r} in [{lo}, {hi}] {axis.unit or ''}".rstrip())
    if inside.ndim == 1 or inside[:, columns].all():
        return _take_columns(var, index, columns)
    # a record-varying axis: values out of range in some records are masked there, not dropped
    values = np.array(var.values, dtype=float)
    values[np.broadcast_to(_along(~inside, index, values.ndim), values.shape)] = np.nan
    return _take_columns(var, index, columns, values)


def _position(axis: VariableAxis, target: float, method: Optional[str]) -> np.ndarray:
    if method == 'nearest':
        return np.nanargmin(np.abs(axis.values - target), axis=-1)
    if method is not None:
        raise ValueError(f"method must be None or 'nearest', got {method!r}")
    hits = axis.values == target
    if not np.all(np.any(hits, axis=-1)):
        raise KeyError(f"{target} is not a value of {axis.name!r}, use method='nearest' for the closest one")
    return np.argmax(hits, axis=-1)


def _sel_value(var, index: int, value, method: Optional[str]):
    position = _position(var.axes[index], float(value), method)
    if position.ndim == 0:
        return _dropped(var, index, np.take(var.values, int(position), axis=index))
    picked = np.take_along_axis(var.values, _along(position[:, None], index, var.values.ndim), axis=index)
    return _dropped(var, index, np.squeeze(picked, axis=index))


def sel(var, axis: Axis, value, method: Optional[str] = None):
    """Select by value, like xarray's sel: a slice or a [lo, hi] pair keeps the values within both bounds (in either
    order, None for no limit on that side; no step); a single value picks it and drops the axis, exactly or with
    ``method='nearest'`` the closest. On a record-varying axis the selection is made per record."""
    index = _reducible(var, axis)
    value = _as_slice(value)
    if isinstance(value, slice):
        return _sel_range(var, index, value.start, value.stop)
    return _sel_value(var, index, value, method)
