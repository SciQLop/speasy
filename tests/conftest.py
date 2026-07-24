import os

import pytest

if "SPEASY_CORE_DISABLED_PROVIDERS" not in os.environ:
        os.environ['SPEASY_CORE_DISABLED_PROVIDERS'] = ""

# Use a headless matplotlib backend for tests; the default (TkAgg on Windows)
# fails on CI runners without a usable Tcl/Tk install.
os.environ.setdefault("MPLBACKEND", "Agg")


@pytest.fixture(autouse=True)
def _close_matplotlib_figures_after_each_test():
    # Plot()'s ax=None path reuses plt.gca() whenever a figure is already open (matching
    # pandas' own convention), so a test that plots without closing its figure silently
    # leaks lines into whichever later test draws next without an explicit ax=.
    yield
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    plt.close("all")
