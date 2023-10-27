import matplotlib.pyplot as plt
import matplotlib.colors as colors
import numpy as np


class Plot:

    def _get_ax(self, ax):
        # ax handling taken from pandas source code here:
        # https://github.com/pandas-dev/pandas/blob/main/pandas/plotting/_matplotlib/__init__.py#L64
        if ax is None and len(plt.get_fignums()) > 0:
            with plt.rc_context():
                ax = plt.gca()
            ax = getattr(ax, "left_ax", ax)
        if ax is None:
            fig, ax = plt.subplots()
        return ax

    def line(self, x, y, ax=None, labels=None, units=None, xaxis_label=None, yaxis_label=None, *args, **kwargs):
        ax = self._get_ax(ax)
        ax.tick_params(axis='x', labelrotation=45)
        ax.plot(x, y, label=labels)
        if labels is not None:
            ax.legend()
        if units is not None and yaxis_label is not None:
            ax.set_ylabel(f"{yaxis_label} ({units})")
        if xaxis_label is not None:
            ax.set_xlabel(f"{xaxis_label}")
        return ax

    def colormap(self, x, y, z, xaxis_label=None, yaxis_label=None, yaxis_units=None, zaxis_label=None,
                 zaxis_units=None, ax=None,
                 cmap=None, logy=True,
                 logz=True, vmin=None, vmax=None, *args,
                 **kwargs):
        ax = self._get_ax(ax)

        if yaxis_units is not None and yaxis_label is not None:
            ax.set_ylabel(f"{yaxis_label} ({yaxis_units})")
        if xaxis_label is not None:
            ax.set_xlabel(f"{xaxis_label}")

        vmin = vmin or np.nanmin(z[np.nonzero(z)])
        vmax = vmax or np.nanmax(z)

        if logy:
            ax.semilogy()
        if logz:
            norm = colors.LogNorm(vmin=vmin, vmax=vmax)
        else:
            norm = colors.Normalize(vmin=vmin, vmax=vmax)

        ax.tick_params(axis='x', labelrotation=45)
        cm = ax.pcolormesh(x, y, z,
                           cmap=cmap or 'plasma',
                           norm=norm, *args, **kwargs)
        cbar = plt.colorbar(cm, ax=ax)
        if zaxis_units is not None and zaxis_label is not None:
            cbar.set_label(f'{zaxis_label} ({zaxis_units})')
        return ax

    def __call__(self, *args, **kwargs):
        pass
