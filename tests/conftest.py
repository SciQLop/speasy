import os

if "SPEASY_CORE_DISABLED_PROVIDERS" not in os.environ:
        os.environ['SPEASY_CORE_DISABLED_PROVIDERS'] = ""

# Use a headless matplotlib backend for tests; the default (TkAgg on Windows)
# fails on CI runners without a usable Tcl/Tk install.
os.environ.setdefault("MPLBACKEND", "Agg")
