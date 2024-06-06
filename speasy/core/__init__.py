"""
.. testsetup:: *

   from speasy.core import *
   import numpy as np
"""

import os
import warnings
from collections.abc import Iterable
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Sequence, Type, Union, Callable

import numpy as np
from dateutil.parser import parse
from tqdm.auto import tqdm

AnyDateTimeType = Union[str, datetime, np.float64, float, np.datetime64]


def deprecation(message: str) -> None:
    """Shows a deprecation warning.

    Parameters
    ----------
    message: str
        Custom message to show
    """

    warnings.warn(message, DeprecationWarning, stacklevel=2)


def pack_kwargs(**kwargs: Any) -> Dict:
    """Packs given keyword arguments into a dictionary

    Parameters
    ----------
    kwargs: Any
        Any keyword argument is accepted

    Returns
    -------
    dict
        A dict with all kwargs packed

    Examples
    --------
    >>> pack_kwargs(a=1, b="2")
    {'a': 1, 'b': '2'}
    """
    return kwargs


def all_of_type(collection: Sequence, expected_type: Type) -> bool:
    """Returns true only if the type of all elements in given collection is expected_type

    Parameters
    ----------
    collection: Sequence
        Any iterable object
    expected_type: Type
        the type you expect to match

    Returns
    -------
    bool
        True only if the type of all elements in given collection is expected_type

    Examples
    --------
    >>> all_of_type([1,2,3], int)
    True

    >>> all_of_type([1,2,3.], int)
    False
    """
    return all(map(lambda x: type(x) is expected_type, collection))


def is_collection(value: Any) -> bool:
    """

    Parameters
    ----------
    value : Any

    Returns
    -------
    bool
        True if given value is collection like object but not a string

    """
    return isinstance(value, Iterable) and type(value) is not str


def mkdir(directory: str) -> None:
    """Creates directory and parents if they do not exist

    Parameters
    ----------
    directory: str
        Path to create
    """
    if not os.path.exists(directory):
        os.makedirs(directory)


def listify(obj: Any) -> List:
    """Wraps inside a list anything that is not a list. Useful in for loops when you can't be sure
    the object you want to iterate is a list.

    Parameters
    ----------
    obj: Any
        Any object or list

    Returns
    -------
    list
        list(obj) if obj is not a list

    Examples
    --------
    >>> for i in listify(1):
    ...     print(i)
    ...
    1

    >>> for i in listify([1,2,3]):
    ...     print(i)
    ...
    1
    2
    3
    """
    obj_t = type(obj)
    if obj_t is list:
        return obj
    if obj_t is tuple:
        return list(obj)
    else:
        return [obj]


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
    datetime.datetime(1970, 1, 1, 0, 0)

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
    numpy.datetime64('2018-01-02T00:00:00.000000000')

    >>> make_utc_datetime64(0.)
    numpy.datetime64('1970-01-01T00:00:00.000000000')

    >>> from datetime import datetime
    >>> make_utc_datetime64(datetime(2020,1,1))
    numpy.datetime64('2020-01-01T00:00:00.000000000')
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


def epoch_to_datetime64(epoch_array: np.array) -> np.array:
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


def datetime64_to_epoch(datetime64_array: np.array) -> np.array:
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
    return (datetime64_array.astype("int64") / 1e-9).astype("float64")


class AllowedKwargs(object):
    """A decorator that prevent from passing unexpected kwargs to a function

    Methods
    -------
    """

    def __init__(self, allowed_list):
        self.allowed_list = set(allowed_list)

    def __call__(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            unexpected_args = list(
                filter(lambda arg_name: arg_name not in self.allowed_list, kwargs.keys()))
            if not unexpected_args:
                return func(*args, **kwargs)
            raise TypeError(
                f"Unexpected keyword argument {unexpected_args}, allowed keyword arguments are {self.allowed_list}")

        return wrapped


def fix_name(name: str):
    """Makes given input compatible with python charset https://docs.python.org/3/reference/lexical_analysis.html#identifiers

    Parameters
    ----------
    name: str
        input string to sanitize

    Returns
    -------
    str
        a string compatible with python naming rules


    Examples
    --------
    >>> fix_name('Parker Solar Probe (PSP)')
    'Parker_Solar_Probe_PSP'

    >>> fix_name('IS⊙ISEPI_Lo')
    'ISoISEPI_Lo'

    >>> fix_name('all_Legal_strings_123')
    'all_Legal_strings_123'

    """
    rules = (
        ('-', '_'),
        (':', '_'),
        ('.', '_'),
        ('(', ''),
        (')', ''),
        ('/', ''),
        (' ', '_'),
        ('{', ''),
        ('}', ''),
        ('(', ''),
        ('⊙', 'o'),
        (';', '_'),
        (',', '_')
    )
    if len(name):
        if name[0].isnumeric():
            name = "n_" + name
        for bad, replacement in rules:
            if bad in name:
                name = name.replace(bad, replacement)
        return name
    raise ValueError("Got empty name")


def progress_bar(leave=True, progress=False, desc=None, **kwargs):
    if not progress:
        return lambda x: x
    else:
        return lambda x: tqdm(x, leave=leave, desc=desc)


class EnsureUTCDateTime(object):

    def __call__(self, get_data: Callable):
        @wraps(get_data)
        def wrapped(wrapped_self, product, start_time, stop_time, **kwargs):
            return get_data(wrapped_self, product=product, start_time=make_utc_datetime(start_time),
                            stop_time=make_utc_datetime(stop_time), **kwargs)

        return wrapped
