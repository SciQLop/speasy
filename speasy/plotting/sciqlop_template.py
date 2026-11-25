"""Reads SciQLop plot panel templates (v2 flat and v3 tree layouts, JSON or YAML) for headless rendering.

Only what Speasy can fetch on its own is kept: speasy products on time series plots. Everything else
(virtual products, plugin plots and panels, ...) is listed in ``Template.skipped`` instead.

A product's optional ``reduce`` key, next to its ``knobs``, is a list of operations applied after ``get_data``, in
order. Each is a dict naming the operation and its arguments, so any tool implements it in a few lines::

    {"op": "isel", "axis": a, "index": i | [start, stop]}
    {"op": "sel", "axis": a, "value": x | [lo, hi], "method": "nearest"}     # method optional
    {"op": "sum", "axis": a}
    {"op": "mean", "axis": a, "weights": [w, ...]}                           # weights optional
    {"op": "integrate", "axis": a, "edges": [e, ...]}                        # edges optional

``a`` is an axis name, a part of one matching a single axis, or a dimension. Here ``isel`` is indexing, ``sel`` and
``integrate`` are :mod:`speasy.signal.reduction`'s, ``sum`` and ``mean`` are numpy's nan-aware ones on the data with
fill values replaced by NaN, NaN where every value is missing. The list is checked at load.

SciQLop and other tools that read templates apply ``reduce`` with :func:`apply_operations`, so a product is reduced
exactly as ``speasy quicklook`` does, and read :data:`OPERATIONS` for the op names.
"""
import json
import os
import warnings
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np
import yaml

from speasy.signal import reduction

__all__ = ['OPERATIONS', 'apply_operations']


SPEASY_PRODUCT_KINDS = ('sciqlop.speasy', 'speasy')
TIME_PANEL = 'sciqlop.time_panel'
TIMESERIES_PLOT = 'sciqlop.timeseries'
# SciQLop knobs that are get_data() keywords of their own; any other knob is an AMDA template input
KNOB_KWARGS = {'ssc': 'coordinate_system', 'cdpp3dview': 'coordinate_frame'}


@dataclass(frozen=True)
class Product:
    speasy_id: str
    label: str = ''
    colormap: bool = False
    right_axis: bool = False
    kwargs: dict = field(default_factory=dict)
    reduce: tuple = ()  # operations applied after get_data, see apply_operations


@dataclass(frozen=True)
class PlotSpec:
    products: Tuple[Product, ...]
    y_log: bool = False
    y2_log: bool = False
    z_log: Optional[bool] = None


@dataclass(frozen=True)
class Template:
    name: str
    time_range: Optional[Tuple[str, str]]
    plots: Tuple[PlotSpec, ...]
    skipped: Tuple[str, ...] = ()


def _isel(var, dimension: int, index):
    return var[(slice(None),) * dimension + (slice(*index) if isinstance(index, (list, tuple)) else index,)]


def _with_nan(var):
    return var.replace_fillval_by_nan(convert_to_float=True)


def _all_missing_as_nan(result, values: np.ndarray, dimension: int):
    result.values[np.all(np.isnan(values), axis=dimension)] = np.nan
    return result


def _sum(var, dimension: int):
    var = _with_nan(var)
    return _all_missing_as_nan(np.nansum(var, axis=dimension), var.values, dimension)


def _weights_along(var, dimension: int, weights) -> np.ndarray:
    weights = np.asarray(getattr(weights, 'values', weights), dtype=float)
    axis = var.axes[dimension]
    if weights.shape != axis.values.shape[-1:]:
        raise ValueError(f"weights for {axis.name!r} must have shape {axis.values.shape[-1:]}, got {weights.shape}")
    shape = [1] * var.values.ndim
    shape[dimension] = weights.shape[0]
    return np.broadcast_to(weights.reshape(shape), var.values.shape)


def _mean(var, dimension: int, weights=None):
    var = _with_nan(var)
    if weights is None:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)  # "Mean of empty slice" where all values are missing
            return np.nanmean(var, axis=dimension)
    weights = np.where(np.isnan(var.values), 0., _weights_along(var, dimension, weights))
    result = np.nansum(var, axis=dimension)
    with np.errstate(invalid='ignore', divide='ignore'):
        result.values[...] = np.nansum(var.values * weights, axis=dimension) / np.sum(weights, axis=dimension)
    return result


#: The ``reduce`` operations, by name: ``(implementation, required keys, optional keys)``. The implementation takes
#: the variable, the dimension the op's ``axis`` resolves to, and the op's other keys. Its keys are the op names
#: SciQLop and other tools accept; the tuples are speasy's own business.
OPERATIONS = {
    'isel': (_isel, ('index',), ()),
    'sel': (reduction.sel, ('value',), ('method',)),
    'sum': (_sum, (), ()),
    'mean': (_mean, (), ('weights',)),
    'integrate': (reduction.integrate, (), ('edges',)),
}


def _usage(name: str) -> str:
    _, required, optional = OPERATIONS[name]
    usage = f"{name} takes " + ', '.join(repr(key) for key in ('axis', *required))
    return usage + (" and optionally " + ', '.join(map(repr, optional)) if optional else '')


def _checked(op: dict) -> dict:
    if not isinstance(op, dict):
        raise ValueError(f"each operation is a dict like {{'op': 'mean', 'axis': 'phi'}}, got {op!r}")
    name = op.get('op')
    if name not in OPERATIONS:
        raise ValueError(f"'op' must be one of {', '.join(OPERATIONS)}, got {op!r}")
    _, required, optional = OPERATIONS[name]
    options = set(op) - {'op', 'axis'}
    if 'axis' not in op or not set(required) <= options <= set(required) | set(optional):
        raise ValueError(f"{_usage(name)}, got {op!r}")
    return op


def checked_operations(operations) -> tuple:
    """Checks a ``reduce`` list without applying it, e.g. when a template is loaded.

    :param operations: a list (or tuple) of dicts, each with ``op``, ``axis`` and that op's keys
    :return: the operations as a tuple
    :raises ValueError: when ``operations`` is not a list, or an op is unknown, misses a key or has an unknown one;
        the message names the op and the keys it takes
    """
    if not isinstance(operations, (list, tuple)):
        raise ValueError(f"expected a list of operations like [{{'op': 'mean', 'axis': 'phi'}}], got {operations!r}")
    return tuple(_checked(op) for op in operations)


def apply_operations(var, operations):
    """Applies a template product's ``reduce`` list to a variable, as ``speasy quicklook`` does.

    SciQLop and other tools that read templates call it, so every tool reduces a product the same way.

    :param var: the :class:`~speasy.products.variable.SpeasyVariable` ``get_data`` returned
    :param operations: the product's ``reduce`` list, applied in order
    :return: the reduced variable; every op returns a new one, ``var`` is left as it was
    :raises ValueError: when the list is malformed (see :func:`checked_operations`, checked before any op runs), or
        an ``axis`` matches no axis, several, or time (see :func:`speasy.signal.reduction.dimension`), or an op
        cannot run on this data, e.g. ``sel`` finds no value in its range
    """
    for op in checked_operations(operations):
        options = {key: value for key, value in op.items() if key not in ('op', 'axis')}
        var = OPERATIONS[op['op']][0](var, reduction.dimension(var, op['axis']), **options)
    return var


class _TemplateLoader(yaml.SafeLoader):
    """SafeLoader that also reads !!python/tuple, as a list: SciQLop before 0.14.2 saved axis ranges as tuples."""


_TemplateLoader.add_constructor('tag:yaml.org,2002:python/tuple',
                                lambda loader, node: loader.construct_sequence(node))


def _read_document(path: str) -> dict:
    with open(path) as f:
        if os.path.splitext(path)[1].lower() == '.json':
            return json.load(f)
        return yaml.load(f, Loader=_TemplateLoader)


def _layout(doc: dict) -> Tuple[Optional[dict], List[Tuple[str, dict]], List[str]]:
    """(time range, [(plot kind, plot config)], skipped) for both the v2 flat and the v3 tree layouts."""
    if doc.get('version', 1) < 3:
        return doc.get('time_range'), [(TIMESERIES_PLOT, p) for p in doc.get('plots', [])], []
    panel = doc['panel']
    if panel.get('kind') != TIME_PANEL:
        return None, [], [f"panel of kind '{panel.get('kind')}': only {TIME_PANEL} panels can be rendered"]
    nodes = panel.get('slots', {}).get('plots', [])
    return panel.get('config', {}).get('time_range'), [(n['kind'], n.get('config', {})) for n in nodes], []


def _kwargs(knobs: dict) -> dict:
    kwargs = {KNOB_KWARGS[k]: v for k, v in knobs.items() if k in KNOB_KWARGS}
    inputs = {k: v for k, v in knobs.items() if k not in KNOB_KWARGS}
    return {**kwargs, **({'product_inputs': inputs} if inputs else {})}


def _speasy_id(product: dict, resolve_path) -> Optional[str]:
    if product.get('speasy_id'):
        return product['speasy_id']
    segments = product.get('path', '').split('//')
    return resolve_path(segments[1:]) if segments[0] == 'speasy' and len(segments) > 1 else None


def _reduce(product: dict, name: str) -> tuple:
    try:
        return checked_operations(product.get('reduce') or [])
    except ValueError as e:
        raise ValueError(f"product {name}: 'reduce': {e}") from None


def _product(product: dict, resolve_path) -> Tuple[Optional[Product], Optional[str]]:
    name = product.get('path') or product.get('label') or product.get('speasy_id') or '<unnamed>'
    if product.get('kind') not in SPEASY_PRODUCT_KINDS:
        return None, f"product {name}: its source is '{product.get('kind')}', only speasy products can be rendered"
    speasy_id = _speasy_id(product, resolve_path)
    if speasy_id is None:
        return None, (f"product {name}: not found in the speasy inventory, "
                      f"saving the template again with a recent SciQLop records its speasy id")
    colormap = 'ColorMap' in product.get('graph_type', '')
    return Product(speasy_id=speasy_id, label=product.get('label', ''), colormap=colormap,
                   right_axis=product.get('y_axis', 'y2' if colormap else 'y') == 'y2',
                   kwargs=_kwargs(product.get('knobs') or {}), reduce=_reduce(product, name)), None


def _log(axis: Optional[dict], default=False):
    return (axis or {}).get('log', default)


def _plot(config: dict, resolve_path) -> Tuple[Optional[PlotSpec], List[str]]:
    results = [_product(p, resolve_path) for p in config.get('products', [])]
    products = tuple(p for p, _ in results if p is not None)
    skipped = [s for _, s in results if s is not None]
    if not products:
        return None, skipped
    return PlotSpec(products=products, y_log=_log(config.get('y_axis')), y2_log=_log(config.get('y2_axis')),
                    z_log=_log(config.get('z_axis'), None)), skipped


def resolve_in_inventory(segments: List[str]) -> Optional[str]:
    """Walks speasy's inventory tree along a SciQLop product path, e.g. ['amda', 'Parameters', ..., 'imf']."""
    import speasy
    node = speasy.inventories.tree
    for segment in segments:
        children = vars(node)
        node = children.get(segment) or next(
            (c for c in children.values() if getattr(c, 'spz_name', lambda: None)() == segment), None)
        if node is None:
            return None
    return f"{node.spz_provider()}/{node.spz_uid()}" if hasattr(node, 'spz_uid') else None


def load_template(path: str, resolve_path: Callable[[List[str]], Optional[str]] = resolve_in_inventory) -> Template:
    doc = _read_document(os.path.expanduser(path))
    if not isinstance(doc, dict) or ('panel' not in doc and 'plots' not in doc):
        raise ValueError(f"{path} is not a SciQLop panel template")
    time_range, nodes, skipped = _layout(doc)
    plots = []
    for kind, config in nodes:
        if kind != TIMESERIES_PLOT:
            skipped.append(f"plot of kind '{kind}': only {TIMESERIES_PLOT} plots can be rendered")
            continue
        plot, plot_skipped = _plot(config, resolve_path)
        skipped.extend(plot_skipped)
        if plot is not None:
            plots.append(plot)
    return Template(name=doc.get('name') or os.path.splitext(os.path.basename(path))[0],
                    time_range=(time_range['start'], time_range['stop']) if time_range else None,
                    plots=tuple(plots), skipped=tuple(skipped))
