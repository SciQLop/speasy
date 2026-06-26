from .istp.cdf import IstpCdf  # noqa: F401
try:
    import netCDF4  # noqa: F401  -- the NetCDF codec needs it (used lazily via pyistp)
    from .istp.netcdf import IstpNetCDF  # noqa: F401
except ImportError:  # pragma: no cover - platform-specific (WASM has no netCDF4 wheel)
    # netCDF4 is unavailable (e.g. WASM/Pyodide, which has no wheel for it):
    # skip the NetCDF codec. CDF reading (pycdfpp) and the rest still work.
    pass
from .hapi.csv import HapiCsv  # noqa: F401
from .hapi.binary import HapiBinary  # noqa: F401
