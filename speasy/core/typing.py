from typing import Union, Any, List, Iterable, Sequence, Type
from datetime import datetime
import numpy as np

AnyDateTimeType = Union[str, datetime, np.float64, float, np.datetime64]

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
    return all(type(x) is expected_type for x in  collection)


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
