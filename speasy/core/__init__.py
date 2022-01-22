"""
.. testsetup:: *

   from speasy.core import *
"""

import os
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, Sequence, Type, List
from functools import wraps

import numpy as np
from dateutil.parser import parse


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


def make_utc_datetime(input_dt: str or datetime or np.float64 or float) -> datetime:
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
        return datetime.utcfromtimestamp(input_dt)
    if type(input_dt) is str:
        input_dt = parse(input_dt)
    return datetime(input_dt.year, input_dt.month, input_dt.day, input_dt.hour, input_dt.minute, input_dt.second,
                    input_dt.microsecond, tzinfo=timezone.utc)


class AllowedKwargs(object):
    """A decorator that prevent from passing unexpected kwargs to a function

    Methods
    -------
    """

    def __init__(self, allowed_list):
        self.allowed_list = allowed_list

    def __call__(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            unexpected_args = list(filter(lambda arg_name: arg_name not in self.allowed_list, kwargs.keys()))
            if not unexpected_args:
                return func(*args, **kwargs)
            raise TypeError(
                f"Unexpected keyword argument {unexpected_args}, allowed keyword arguments are {self.allowed_list}")

        return wrapped
