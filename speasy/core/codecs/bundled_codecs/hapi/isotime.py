import re
from datetime import date, datetime, timedelta

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


_HOUR_24 = re.compile(r"^(\d{4}-\d{2}-\d{2})T24(?::00)*(?:\.0*)?$")
_LEAP_SECOND = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}):60(?:\.\d*)?$")


def calendar_isotime(isotime: str) -> str:
    """HAPI allows day-of-year dates, hour 24 and leap seconds, which neither numpy nor dateutil parse. Hour 24 is the
    next day's midnight, and a leap second becomes the start of the next minute (dropping up to a second)."""
    t = day_of_year_to_calendar(isotime)
    if m := _HOUR_24.match(t):
        return (date.fromisoformat(m[1]) + timedelta(days=1)).isoformat() + "T00:00"
    if m := _LEAP_SECOND.match(t):
        return (datetime.fromisoformat(m[1]) + timedelta(minutes=1)).isoformat(timespec="minutes")
    return t


def parse_isotime(values: np.ndarray) -> np.ndarray:
    strings = np.char.rstrip(np.char.strip(np.asarray(values).astype(str)), "Z")
    try:
        return strings.astype("datetime64[ns]")
    except ValueError:
        # simplify: per-value Python conversion, fine for the few servers sending such times; vectorize if that changes.
        return np.array([calendar_isotime(t) for t in strings.flat]).reshape(strings.shape).astype("datetime64[ns]")
