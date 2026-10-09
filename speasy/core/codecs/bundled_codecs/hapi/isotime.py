import numpy as np

# "YYYY-MM-DDTHH:MM:SS" + "." + fractional digits + "Z"
_BASE_LENGTH = len("1970-01-01T00:00:00.Z")
_UNITS = {"ms": 3, "us": 6, "ns": 9}


def isotime_unit(values: np.ndarray) -> str:
    """Coarsest of ms/us/ns that still represents every timestamp exactly (ms when empty)."""
    ns = values.astype("datetime64[ns]").view(np.int64)
    for unit, step in (("ms", 1_000_000), ("us", 1_000)):
        if not np.any(ns % step):
            return unit
    return "ns"


def isotime_length(unit: str) -> int:
    return _BASE_LENGTH + _UNITS[unit]


def isotime_unit_from_length(length: int) -> str:
    for unit, digits in _UNITS.items():
        if _BASE_LENGTH + digits == length:
            return unit
    raise ValueError(f"Unsupported isotime length {length}")


def format_isotime(values: np.ndarray, length: int) -> np.ndarray:
    """ISO-8601 UTC strings of exactly `length` characters, as declared in the parameter's metadata."""
    unit = isotime_unit_from_length(length)
    return np.char.add(np.datetime_as_string(values.astype(f"datetime64[{unit}]"), unit=unit), "Z")
