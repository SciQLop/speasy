import re
from dataclasses import dataclass

import numpy as np

from .mpl_backend import Plot as MplPlot
from ..core.data_containers import DataContainer, VariableAxis, VariableTimeAxis, fill_value_mask
from .istp_hints import is_log_scale, label_from_meta
from typing import List
from enum import Enum
from copy import copy

__backends__ = {
    "matplotlib": MplPlot,
    None: MplPlot
}


class PlotType(Enum):
    LINE = 0
    SPECTRO = 1


# CDAWeb spells the type first and its options after '>', as in 'spectrogram>y=Center_Scan, z=...'
# or 'map_image>THUMBSIZE>166>MAP_PROJ>7>SMOOTH>x=latitude,y=longitude'
_axis_hint_regex = re.compile(r"\b([xy])\s*=\s*([^,>\s]+)")


def _display_type(meta) -> str:
    return meta.get("DISPLAY_TYPE", "").split(">")[0].strip().lower()


def _axes_named_by_hint(meta) -> dict:
    return dict(_axis_hint_regex.findall(meta.get("DISPLAY_TYPE", "")))


def _at_time(axis, index: int):
    return axis.values[index] if axis.is_time_dependent else axis.values


@dataclass
class Plot:
    axes: List[VariableAxis or VariableTimeAxis]
    values: DataContainer
    columns_names: List[str]

    def _set_backend(self, name=None):
        if not hasattr(self, "_backend") or name != self._backend_name or self._backend_name is None:
            self._backend_name = name or "matplotlib"
            self._backend = __backends__[self._backend_name]()

    def _get_backend(self, name=None):
        self._set_backend(name)
        return self._backend

    def _with_backend(self, backend):
        new = copy(self)
        new._set_backend(backend)
        return new

    def _masked_values(self):
        """Values with ISTP fill entries replaced by NaN, so a sentinel never reaches the axes."""
        values = self.values.values
        mask = fill_value_mask(values, self.values.meta)
        return values if mask is None else np.where(mask, np.nan, values)

    def _infer_plot_type(self):
        if _display_type(self.values.meta) in ("spectrogram", "map_image", "map_movie"):
            return PlotType.SPECTRO
        return PlotType.LINE

    def _coordinate_grid_axes(self):
        """The grids to spread over, in the order the hint asks for, else in array order."""
        hint = _axes_named_by_hint(self.values.meta)
        by_name = {axis.name: axis for axis in self.axes[1:]}
        return by_name.get(hint.get('x'), self.axes[-1]), by_name.get(hint.get('y'), self.axes[-2])

    def line(self, *args, backend=None, **kwargs):
        units = kwargs.pop("units", None) or self.values.unit
        labels = kwargs.pop("labels", None) or self.columns_names
        xaxis_label = kwargs.pop("xaxis_label", None) or self.axes[0].name
        yaxis_label = kwargs.pop("yaxis_label", None) or label_from_meta(self.values.meta) or self.values.name
        logy = kwargs.pop("logy", None)
        if logy is None:
            logy = is_log_scale(self.values.meta)
        if logy is None:
            logy = False
        mask_fillval = kwargs.pop("mask_fillval", True)
        y = self._masked_values() if mask_fillval else self.values.values
        return self._get_backend(backend).line(x=self.axes[0].values, y=y, labels=labels,
                                               units=units,
                                               xaxis_label=xaxis_label,
                                               yaxis_label=yaxis_label,
                                               logy=logy, *args,
                                               **kwargs)

    def _spread_over_coordinate_grids(self) -> bool:
        """Do the extra axes give a coordinate per data cell rather than one value per index?

        That is how CDAWeb ships map products: latitude and longitude cover the whole grid, so
        there is no axis left to put time on and the colormap shows one time step instead. Every
        remaining dimension needs one, otherwise there is nothing to spread the field over: PSP's
        energy grid sits next to a plain look direction axis and is a spectrogram, not a map.
        """
        shape = self.values.values.shape
        return len(shape) > 2 and all(axis.values.shape in (shape, shape[1:]) for axis in self.axes[1:])

    def _grids_arrangement(self, values, time_index: int, logy) -> dict:
        x_axis, y_axis = self._coordinate_grid_axes()
        return {
            "x": _at_time(x_axis, time_index), "y": _at_time(y_axis, time_index), "z": values[time_index],
            "xaxis_label": label_from_meta(x_axis.meta) or x_axis.name,
            "yaxis_label": label_from_meta(y_axis.meta) or y_axis.name,
            "yaxis_units": y_axis.unit,
            "logy": False if logy is None else logy,
        }

    def _time_arrangement(self, values, logy) -> dict:
        if logy is None:
            logy = is_log_scale(self.axes[1].meta)
        if logy is None:
            logy = True
        return {
            "x": self.axes[0].values, "y": self.axes[1].values.T, "z": values.T,
            "xaxis_label": self.axes[0].name,
            "yaxis_label": label_from_meta(self.axes[1].meta) or self.axes[1].name,
            "yaxis_units": self.axes[1].unit,
            "logy": logy,
        }

    def colormap(self, *args, logy=None, logz=None, time_index: int = 0, backend=None, **kwargs):
        """Colours a 2D field: time against an axis, or one time step over two coordinate grids."""
        mask_fillval = kwargs.pop("mask_fillval", True)
        values = self._masked_values() if mask_fillval else self.values.values
        if self._spread_over_coordinate_grids():
            arrangement = self._grids_arrangement(values, time_index, logy)
        elif values.ndim > 2:
            raise ValueError(
                f"A colormap needs 2 dimensions, got {values.ndim} dimensions {self.values.shape} "
                f"and axes describing one value per index. Reduce a dimension first, for instance "
                f"with numpy.sum(variable, axis=1)."
            )
        else:
            arrangement = self._time_arrangement(values, logy)
        for key in ("xaxis_label", "yaxis_label", "yaxis_units"):
            arrangement[key] = kwargs.pop(key, None) or arrangement[key]
        zaxis_units = kwargs.pop("zaxis_units", None) or self.values.unit
        zaxis_label = kwargs.pop("zaxis_label", None) or label_from_meta(self.values.meta) or self.values.name
        if logz is None:
            logz = is_log_scale(self.values.meta)
        if logz is None:
            logz = True
        return self._get_backend(backend).colormap(*args,
                                                   zaxis_label=zaxis_label,
                                                   zaxis_units=zaxis_units,
                                                   logz=logz, **arrangement, **kwargs)

    def __call__(self, *args, backend=None, **kwargs):
        if self._infer_plot_type() == PlotType.SPECTRO:
            return self.colormap(backend=backend, *args, **kwargs)
        return self.line(backend=backend, *args, **kwargs)

    def __getitem__(self, item):
        assert type(item) is str
        return self._with_backend(item)
