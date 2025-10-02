from typing import Callable
from datetime import datetime, timezone
from functools import wraps
import numpy as np
from dateutil.parser import parse
from .typing import AnyDateTimeType


def make_utc_datetime(input_dt: AnyDateTimeType) -> datetime:
    """Makes UTC datetime from given input.

    Parameters
    ----------
    input_dt: str or datetime or np.float64 or float
        Datetime to convert, can be either en Epoch, a datetime or a string

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
    """
    if type(input_dt) in (np.float64, float):
        return datetime.fromtimestamp(input_dt, tz=timezone.utc)
    if type(input_dt) is str:
        input_dt = parse(input_dt)
    if type(input_dt) is np.datetime64:
        if input_dt.dtype == np.dtype('datetime64[ns]'):
            return datetime.fromtimestamp(input_dt.astype(np.int64) * 1e-9, tz=timezone.utc)

    return datetime(input_dt.year, input_dt.month, input_dt.day, input_dt.hour, input_dt.minute, input_dt.second,
                    input_dt.microsecond, tzinfo=timezone.utc)


def make_utc_datetime64(input_dt: AnyDateTimeType) -> np.datetime64:
    """Makes UTC np.datetime64 from given input.

    Parameters
    ----------
    input_dt: str or datetime or np.float64 or float
        Datetime to convert, can be either en Epoch, a datetime or a string

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
    """
    if type(input_dt) in (np.float64, float):
        return np.datetime64(datetime.fromtimestamp(input_dt, tz=timezone.utc))
    if type(input_dt) is str:
        input_dt = parse(input_dt)
    if type(input_dt) is np.datetime64:
        if input_dt.dtype == np.dtype('datetime64[ns]'):
            return input_dt

    return np.datetime64(
        datetime(input_dt.year, input_dt.month, input_dt.day, input_dt.hour, input_dt.minute, input_dt.second,
                 input_dt.microsecond, tzinfo=timezone.utc), 'ns')


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
