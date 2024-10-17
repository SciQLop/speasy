from dataclasses import dataclass

from .mpl_backend import Plot as MplPlot
from ..core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
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

    def _infer_plot_type(self):
        if self.values.meta.get("DISPLAY_TYPE", "").lower() == "spectrogram":
            return PlotType.SPECTRO
        return PlotType.LINE

    def line(self, *args, backend=None, **kwargs):
        units = kwargs.pop("units", None) or self.values.unit
        labels = kwargs.pop("labels", None) or self.columns_names
        xaxis_label = kwargs.pop("xaxis_label", None) or self.axes[0].name
        yaxis_label = kwargs.pop("yaxis_label", None) or self.values.name
        return self._get_backend(backend).line(x=self.axes[0].values, y=self.values.values, labels=labels,
                                               units=units,
                                               xaxis_label=xaxis_label,
                                               yaxis_label=yaxis_label, *args,
                                               **kwargs)

    def colormap(self, *args, logy=True, logz=True, backend=None, **kwargs):
        x_axis_label = kwargs.pop("xaxis_label", None) or self.axes[0].name
        yaxis_units = kwargs.pop("yaxis_units", None) or self.axes[1].unit
        yaxis_label = kwargs.pop("yaxis_label", None) or self.axes[1].name
        zaxis_units = kwargs.pop("zaxis_units", None) or self.values.unit
        zaxis_label = kwargs.pop("zaxis_label", None) or self.values.name
        return self._get_backend(backend).colormap(x=self.axes[0].values, y=self.axes[1].values.T,
                                                   z=self.values.values.T,
                                                   xaxis_label=x_axis_label,
                                                   yaxis_label=yaxis_label,
                                                   yaxis_units=yaxis_units,
                                                   zaxis_label=zaxis_label,
                                                   zaxis_units=zaxis_units,
                                                   logy=logy,
                                                   logz=logz, *args, **kwargs)

    def __call__(self, *args, backend=None, **kwargs):
        if self._infer_plot_type() == PlotType.SPECTRO:
            return self.colormap(backend=backend, *args, **kwargs)
        return self.line(backend=backend, *args, **kwargs)

    def __getitem__(self, item):
        assert type(item) is str
        return self._with_backend(item)
