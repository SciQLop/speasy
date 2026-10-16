"""Reads SciQLop plot panel templates (v2 flat and v3 tree layouts, JSON or YAML) for headless rendering.

Only what Speasy can fetch on its own is kept: speasy products on time series plots. Everything else
(virtual products, plugin plots and panels, ...) is listed in ``Template.skipped`` instead.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import yaml

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


def _product(product: dict, resolve_path) -> Tuple[Optional[Product], Optional[str]]:
    name = product.get('path') or product.get('label') or '<unnamed>'
    if product.get('kind') not in SPEASY_PRODUCT_KINDS:
        return None, f"product {name}: its source is '{product.get('kind')}', only speasy products can be rendered"
    speasy_id = _speasy_id(product, resolve_path)
    if speasy_id is None:
        return None, (f"product {name}: not found in the speasy inventory, "
                      f"saving the template again with a recent SciQLop records its speasy id")
    colormap = 'ColorMap' in product.get('graph_type', '')
    return Product(speasy_id=speasy_id, label=product.get('label', ''), colormap=colormap,
                   right_axis=product.get('y_axis', 'y2' if colormap else 'y') == 'y2',
                   kwargs=_kwargs(product.get('knobs') or {})), None


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
