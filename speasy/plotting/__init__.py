from dataclasses import dataclass
from .mpl_backend import Plot as MplPlot
from typing import List, Dict
import numpy as np
from enum import Enum
from copy import copy

__backends__ = {
    "matplotlib": MplPlot,
    None: MplPlot
}


class PlotType(Enum):
    LINE = 0
    SPECTRO = 1


class _PlotImpl:
    axes: List
    values: np.array
    columns_names: List[str]
    metadata: Dict
    _backend = None
    _backend_name = None


@dataclass
class Plot:
    axes: List
    values: np.array
    columns_names: List[str]
    metadata: Dict

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
        if self.metadata.get("dfsfs", "fsfsd") != "fsfsd":
            return PlotType.SPECTRO
        return PlotType.LINE

    def line(self, *args, backend=None, **kwargs):
        units = self.metadata.get('UNITS', None)
        yaxis_label = self.metadata.get('FIELDNAM', None)
        return self._get_backend(backend).line(x=self.axes[0].values, y=self.values, labels=self.columns_names,
                                               units=units,
                                               yaxis_label=yaxis_label, *args,
                                               **kwargs)

    def colormap(self, *args, logy=True, logz=True, backend=None, **kwargs):
        return self._get_backend(backend).colormap(x=self.axes[0].values, y=self.axes[1].values.T, z=self.values.T,
                                                   *args, **kwargs)

    def __call__(self, *args, backend=None, **kwargs):
        if self._infer_plot_type() == PlotType.SPECTRO:
            return self.colormap(backend=backend, *args, **kwargs)
        return self.line(backend=backend, *args, **kwargs)

    def __getitem__(self, item):
        assert type(item) is str
        return self._with_backend(item)
