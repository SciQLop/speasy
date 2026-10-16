"""Headless quicklooks: one image per time window from a SciQLop plot template, with matplotlib."""
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

import matplotlib
import numpy as np
from cycler import cycler
from matplotlib.figure import Figure

from speasy.core import AnyDateTimeType, make_utc_datetime
from speasy.core.direct_archive_downloader.direct_archive_downloader import spilt_range
from .sciqlop_template import PlotSpec, Template


def windows(start: AnyDateTimeType, stop: AnyDateTimeType, split: str) -> List[Tuple[datetime, datetime]]:
    """Calendar-aligned windows ('daily', 'monthly', 'yearly' or 'none') covering [start, stop), clipped to it."""
    start, stop = make_utc_datetime(start), make_utc_datetime(stop)
    starts = [max(s, start) for s in spilt_range(split, start, stop)]
    return [(s, e) for s, e in zip(starts, [*starts[1:], stop]) if s < e]


def _has_data(var) -> bool:
    return var is not None and len(var) > 0


def _draw_one(ax, product, var, plot: PlotSpec):
    logy = plot.y2_log if product.right_axis else plot.y_log
    if product.colormap:
        var.plot.colormap(ax=ax, logy=logy, logz=plot.z_log)
    else:
        var.plot.line(ax=ax, logy=logy)


def _rotated_color_cycle(offset: int):
    """The default colour cycle, starting after the colours the left axis already used."""
    colors = matplotlib.rcParams['axes.prop_cycle'].by_key()['color']
    offset %= len(colors)
    return cycler(color=colors[offset:] + colors[:offset])


def _merge_legends(ax, twin):
    handles, labels = ax.get_legend_handles_labels()
    twin_handles, twin_labels = twin.get_legend_handles_labels()
    if twin.get_legend() is not None:
        twin.get_legend().remove()
    ax.legend(handles + twin_handles, labels + twin_labels)


def _on_right_axis(product) -> bool:
    return product.right_axis and not product.colormap  # a colormap always fills the main axes


def _draw(ax, plot: PlotSpec, variables: Sequence):
    # simplify: saved axis ranges are ignored, they are one zoom level and would clip other windows
    drawn = [(product, var) for product, var in zip(plot.products, variables) if _has_data(var)]
    on_right = [(p, v) for p, v in drawn if _on_right_axis(p)]
    for product, var in drawn:
        if not _on_right_axis(product):
            _draw_one(ax, product, var, plot)
    if on_right:
        twin = ax.twinx()
        twin.set_prop_cycle(_rotated_color_cycle(len(ax.get_lines())))
        for product, var in on_right:
            _draw_one(twin, product, var, plot)
        _merge_legends(ax, twin)
    if not drawn:
        ax.text(0.5, 0.5, 'no data', transform=ax.transAxes, ha='center', va='center')


def _fetch(product, start: datetime, stop: datetime) -> Tuple[Optional[object], Optional[str]]:
    import speasy
    try:
        return speasy.get_data(product.speasy_id, start, stop, **product.kwargs), None
    except Exception as e:  # one failing product must not cost the whole quicklook
        return None, f"{product.speasy_id}: {type(e).__name__}: {e}"


def fetch_window(template: Template, start: datetime, stop: datetime) -> Tuple[list, List[str]]:
    """(data for render(), failure messages) for one window."""
    results = [[_fetch(product, start, stop) for product in plot.products] for plot in template.plots]
    return [[var for var, _ in plot] for plot in results], [f for plot in results for _, f in plot if f]


def _naive_utc(t: datetime) -> np.datetime64:
    return np.datetime64(t.replace(tzinfo=None))  # the data time axes are naive UTC datetime64


def figure(template: Template, data: Sequence[Sequence[Optional[object]]], start: datetime, stop: datetime,
           width: float = 12, plot_height: float = 2.5) -> Figure:
    """Draws one window: data[i][j] is the variable of template.plots[i].products[j], None when missing.

    Uses a bare matplotlib Figure, never pyplot, so batches leave no figure behind.
    """
    fig = Figure(figsize=(width, plot_height * len(template.plots)), layout='constrained')
    axes = fig.subplots(len(template.plots), 1, sharex=True, squeeze=False)[:, 0]
    for ax, plot, variables in zip(axes, template.plots, data):
        _draw(ax, plot, variables)
    for ax in axes[:-1]:  # the shared time axis only needs its label once, at the bottom
        ax.set_xlabel('')
    axes[-1].set_xlim(_naive_utc(start), _naive_utc(stop))
    fig.suptitle(f"{template.name}  {start:%Y-%m-%d %H:%M} → {stop:%Y-%m-%d %H:%M} UTC")
    return fig


def render(template: Template, data: Sequence[Sequence[Optional[object]]], start: datetime, stop: datetime,
           path: str):
    figure(template, data, start, stop).savefig(path)
