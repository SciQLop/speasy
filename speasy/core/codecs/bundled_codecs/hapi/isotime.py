import re
from datetime import datetime

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


_DAY_OF_YEAR = re.compile(r"^(\d{4})-(\d{3})(T.*)?$")


def day_of_year_to_calendar(isotime: str) -> str:
    """'2015-032T01:00' -> '2015-02-01T01:00', other times are returned as is."""
    m = _DAY_OF_YEAR.match(isotime)
    if m is None:
        return isotime
    return datetime.strptime(m[1] + m[2], "%Y%j").strftime("%Y-%m-%d") + (m[3] or "")


def parse_isotime(values: np.ndarray) -> np.ndarray:
    """HAPI isotimes may use day-of-year dates (YYYY-DDD), which numpy can't parse."""
    strings = np.char.rstrip(np.char.strip(np.asarray(values).astype(str)), "Z")
    if strings.size and _DAY_OF_YEAR.match(str(strings.flat[0])):
        # simplify: per-value Python conversion, fine for the few small day-of-year servers; vectorize if that changes.
        strings = np.array([day_of_year_to_calendar(t) for t in strings.flat]).reshape(strings.shape)
    return strings.astype("datetime64[ns]")
