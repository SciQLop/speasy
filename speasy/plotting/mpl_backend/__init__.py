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

    def line(self, x, y, ax=None, labels=None, units=None, xaxis_label=None, yaxis_label=None, logy=False, *args,
             **kwargs):
        ax = self._get_ax(ax)
        ax.tick_params(axis='x', labelrotation=45)
        ax.plot(x, y, label=labels, *args, **kwargs)
        if labels is not None:
            ax.legend()
        if units is not None and yaxis_label is not None:
            ax.set_ylabel(f"{yaxis_label} ({units})")
        if xaxis_label is not None:
            ax.set_xlabel(f"{xaxis_label}")
        if logy:
            ax.semilogy()
        return ax

    def _mesh(self, ax, x, y, z, *args, **kwargs):
        """Cells the instrument was not looking through carry no coordinate at all.

        pcolormesh refuses non-finite coordinates outright rather than skipping those cells, while
        pcolor drops just the quads it cannot place, so a punctured grid goes through pcolor.
        """
        if np.all(np.isfinite(x)) and np.all(np.isfinite(y)):
            return ax.pcolormesh(x, y, z, *args, **kwargs)
        return ax.pcolor(np.ma.masked_invalid(x), np.ma.masked_invalid(y), z, *args, **kwargs)

    def _norm(self, z, logz, vmin, vmax):
        # A log scale cannot place zero or negative values, so it scales from the smallest
        # positive one, while a linear scale uses them all. A slice left with nothing to scale
        # from -- entirely masked/FILLVAL, or all zeros on a log scale -- falls back to bounds
        # matplotlib accepts rather than NaN or inverted ones.
        finite = z[np.isfinite(z)]
        scalable = finite[finite > 0] if logz else finite
        if not len(scalable):
            scalable = np.array([1., 10.])
        if vmin is None:
            vmin = scalable.min()
        if vmax is None:
            vmax = scalable.max()
        if logz:
            return colors.LogNorm(vmin=vmin, vmax=vmax)
        return colors.Normalize(vmin=vmin, vmax=vmax)

    def colormap(self, x, y, z, xaxis_label=None, yaxis_label=None, yaxis_units=None, zaxis_label=None,
                 zaxis_units=None, ax=None,
                 cmap=None, logy=True,
                 logz=True, vmin=None, vmax=None, *args,
                 **kwargs):
        ax = self._get_ax(ax)

        if yaxis_label is not None:
            ax.set_ylabel(f"{yaxis_label} ({yaxis_units})" if yaxis_units else yaxis_label)
        if xaxis_label is not None:
            ax.set_xlabel(f"{xaxis_label}")

        if logy:
            ax.semilogy()
        norm = self._norm(z, logz, vmin, vmax)

        if np.issubdtype(np.asarray(x).dtype, np.datetime64):   # dates need the room, degrees don't
            ax.tick_params(axis='x', labelrotation=45)
        cm = self._mesh(ax, x, y, z,
                        cmap=cmap or 'plasma',
                        norm=norm, *args, **kwargs)
        cbar = plt.colorbar(cm, ax=ax)
        if zaxis_units is not None and zaxis_label is not None:
            cbar.set_label(f'{zaxis_label} ({zaxis_units})')
        return ax

    def __call__(self, *args, **kwargs):
        pass
