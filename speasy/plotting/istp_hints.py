"""ISTP metadata -> plot configuration hints.

Maps ISTP attributes already present on a fetched SpeasyVariable's meta dict (SCALETYP,
FILLVAL, LABLAXIS) to plotting defaults, mirroring SciQLop's istp_hints -> PlotHints
translation. A hint only fills in what the caller left unset -- callers always let an
explicit keyword argument win.
"""
from typing import Optional

import numpy as np


def _scalar_meta(meta: dict, key: str):
    value = meta.get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def scale_type_from_meta(meta: dict) -> Optional[str]:
    """Returns 'log' or 'linear' from the ISTP SCALETYP attribute, or None if absent/unrecognized."""
    scaletyp = _scalar_meta(meta, "SCALETYP")
    if isinstance(scaletyp, str) and scaletyp.lower() in ("log", "linear"):
        return scaletyp.lower()
    return None


def is_log_scale(meta: dict) -> Optional[bool]:
    """Returns True/False from SCALETYP, or None if the metadata doesn't say."""
    scale = scale_type_from_meta(meta)
    return None if scale is None else scale == "log"


def label_from_meta(meta: dict) -> Optional[str]:
    """Returns the ISTP LABLAXIS attribute, or None if absent."""
    label = _scalar_meta(meta, "LABLAXIS")
    return label if isinstance(label, str) and label else None


def mask_fill_values(values: np.ndarray, meta: dict) -> np.ndarray:
    """Returns values with FILLVAL entries replaced by NaN (a new array when masking occurs,
    the same array unchanged when there's nothing to mask).

    No-op if FILLVAL is absent, or if FILLVAL is itself NaN (some providers, e.g. AMDA,
    use NaN directly as the fill sentinel, so there's nothing left to mask).
    """
    fillval = _scalar_meta(meta, "FILLVAL")
    if fillval is None or (isinstance(fillval, float) and np.isnan(fillval)):
        return values
    return np.where(values == fillval, np.nan, values)
