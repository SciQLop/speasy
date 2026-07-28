"""ISTP metadata -> plot configuration hints.

Maps ISTP attributes already present on a fetched SpeasyVariable's meta dict (SCALETYP,
FILLVAL, LABLAXIS) to plotting defaults, mirroring SciQLop's istp_hints -> PlotHints
translation. A hint only fills in what the caller left unset -- callers always let an
explicit keyword argument win.
"""
from typing import Optional

from ..core.data_containers import scalar_meta


def scale_type_from_meta(meta: dict) -> Optional[str]:
    """Returns 'log' or 'linear' from the ISTP SCALETYP attribute, or None if absent/unrecognized."""
    scaletyp = scalar_meta(meta, "SCALETYP")
    if isinstance(scaletyp, str) and scaletyp.lower() in ("log", "linear"):
        return scaletyp.lower()
    return None


def is_log_scale(meta: dict) -> Optional[bool]:
    """Returns True/False from SCALETYP, or None if the metadata doesn't say."""
    scale = scale_type_from_meta(meta)
    return None if scale is None else scale == "log"


def label_from_meta(meta: dict) -> Optional[str]:
    """Returns the ISTP LABLAXIS attribute, or None if absent."""
    label = scalar_meta(meta, "LABLAXIS")
    return label if isinstance(label, str) and label else None
