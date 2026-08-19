"""
.. testsetup:: *

   from speasy.core.time import *
   import numpy as np
"""
from typing import Callable
from datetime import datetime, timezone
from functools import wraps
import numpy as np
from dateutil.parser import parse
from .typing import AnyDateTimeType

# numpy wraps around int64 instead of raising when a date falls outside the datetime64[ns]
# range, silently returning a wrong date, so conversions have to check for themselves.
# Bounds are the real ones rounded inwards to the microsecond, the finest resolution any
# input can carry once parsed.
_NS_RANGE = (np.datetime64('1677-09-21T00:12:43.145225'), np.datetime64('2262-04-11T23:47:16.854775'))


def _to_datetime64_ns(input_dt: datetime) -> np.datetime64:
    value = np.datetime64(input_dt, 'us')
    if not (_NS_RANGE[0] <= value <= _NS_RANGE[1]):
        raise ValueError(
            f"{input_dt} is outside the datetime64[ns] range Speasy uses ({_NS_RANGE[0]} to {_NS_RANGE[1]})")
    return value.astype('datetime64[ns]')


def make_utc_datetime(input_dt: AnyDateTimeType) -> datetime:
    """Makes UTC datetime from given input.

    Parameters
    ----------
    input_dt: str or datetime or np.datetime64 or np.float64 or float
        Datetime to convert, can be either an Epoch, a datetime, a numpy datetime64 (any unit)
        or a string. Naive datetimes and strings without timezone information are assumed to be UTC,
        timezone aware ones are converted to UTC.

    Returns
    -------
    datetime
        A datetime.datetime object forced to UTC time zone

    Examples
    --------
    >>> make_utc_datetime('2018-01-02')
    datetime.datetime(2018, 1, 2, 0, 0, tzinfo=datetime.timezone.utc)

    >>> make_utc_datetime(0.)
    datetime.datetime(1970, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)

    >>> from datetime import datetime
    >>> make_utc_datetime(datetime(2020,1,1))
    datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)

    >>> make_utc_datetime(np.datetime64('2016-06-02'))
    datetime.datetime(2016, 6, 2, 0, 0, tzinfo=datetime.timezone.utc)

    >>> make_utc_datetime('2018-01-01T01:00:00+02:00')
    datetime.datetime(2017, 12, 31, 23, 0, tzinfo=datetime.timezone.utc)
    """
    if type(input_dt) in (np.float64, float):
        return datetime.fromtimestamp(input_dt, tz=timezone.utc)
    if type(input_dt) is str:
        input_dt = parse(input_dt)
    if type(input_dt) is np.datetime64:
        if input_dt.dtype == np.dtype('datetime64[ns]'):
            return datetime.fromtimestamp(input_dt.astype(np.int64) * 1e-9, tz=timezone.utc)
        # going through datetime64[us] first allows any input unit without
        # overflowing int64 for realistic dates
        input_dt = input_dt.astype('datetime64[us]').astype(datetime)
    if isinstance(input_dt, datetime):
        if input_dt.tzinfo is not None:
            return input_dt.astimezone(timezone.utc)
        return input_dt.replace(tzinfo=timezone.utc)
    raise TypeError(f"Unsupported datetime type: {type(input_dt)}, expected str, datetime, np.datetime64 or float")


def make_utc_datetime64(input_dt: AnyDateTimeType) -> np.datetime64:
    """Makes UTC np.datetime64 from given input.

    Parameters
    ----------
    input_dt: str or datetime or np.datetime64 or np.float64 or float
        Datetime to convert, can be either an Epoch, a datetime, a numpy datetime64 (any unit)
        or a string. Naive datetimes and strings without timezone information are assumed to be UTC,
        timezone aware ones are converted to UTC.

    Returns
    -------
    np.datetime64
        A numpy datetime64 object forced to UTC time zone

    Examples
    --------
    >>> make_utc_datetime64('2018-01-02')
    np.datetime64('2018-01-02T00:00:00.000000000')

    >>> make_utc_datetime64(0.)
    np.datetime64('1970-01-01T00:00:00.000000')

    >>> from datetime import datetime
    >>> make_utc_datetime64(datetime(2020,1,1))
    np.datetime64('2020-01-01T00:00:00.000000000')

    >>> make_utc_datetime64(np.datetime64('2016-06-02'))
    np.datetime64('2016-06-02T00:00:00.000000000')

    >>> make_utc_datetime64('2018-01-01T01:00:00+02:00')
    np.datetime64('2017-12-31T23:00:00.000000000')
    """
    if type(input_dt) in (np.float64, float):
        return np.datetime64(datetime.fromtimestamp(input_dt, tz=timezone.utc))
    if type(input_dt) is str:
        input_dt = parse(input_dt)
    if type(input_dt) is np.datetime64:
        if input_dt.dtype == np.dtype('datetime64[ns]'):
            return input_dt
        # going through datetime64[us] first allows any input unit without
        # overflowing int64 for realistic dates
        input_dt = input_dt.astype('datetime64[us]').astype(datetime)
    if isinstance(input_dt, datetime):
        if input_dt.tzinfo is not None:
            input_dt = input_dt.astimezone(timezone.utc).replace(tzinfo=None)
        return _to_datetime64_ns(input_dt)
    raise TypeError(f"Unsupported datetime type: {type(input_dt)}, expected str, datetime, np.datetime64 or float")


def epoch_to_datetime64(epoch_array: np.ndarray) -> np.ndarray:
    """Converts an array of floats encoded as Unix Epoch (seconds since 1970) to an array of numpy datetime64[ns]

    Parameters
    ----------
    epoch_array : np.array
        Input array of folats (Epoch)

    Returns
    -------
    np.array
        Output array of datetime64[ns]

    Examples
    --------
    >>> epoch_to_datetime64(np.arange(2))
    array(['1970-01-01T00:00:00.000000000', '1970-01-01T00:00:01.000000000'],
          dtype='datetime64[ns]')


    """
    return (epoch_array * 1e9).astype("datetime64[ns]")


def datetime64_to_epoch(datetime64_array: np.ndarray) -> np.ndarray:
    """Converts an array of numpy datetime64[ns] to an array of floats encoded as Unix Epoch (seconds since 1970)

    Parameters
    ----------
    datetime64_array : np.array
        Input array of datetime64[ns]

    Returns
    -------
    np.array
        Output array of floats (Epoch)

    Examples
    --------
    >>> datetime64_to_epoch(np.array(['1970-01-01T00:00:00.000000000', '1970-01-01T00:00:01.000000000'],
    ...                              dtype='datetime64[ns]'))
    array([0., 1.])
    """
    return (datetime64_array.astype("int64") * 1e-9).astype("float64")



class EnsureUTCDateTime(object):

    def __call__(self, get_data: Callable):
        @wraps(get_data)
        def wrapped(wrapped_self, product, start_time, stop_time, **kwargs):
            return get_data(wrapped_self, product=product, start_time=make_utc_datetime(start_time),
                            stop_time=make_utc_datetime(stop_time), **kwargs)

        return wrapped
