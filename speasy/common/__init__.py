from datetime import datetime, timezone
from dateutil.parser import parse
import os
import warnings
import numpy as np


def listify(obj: list or tuple or object) -> list:
    obj_t = type(obj)
    if obj_t is list:
        return obj
    if obj_t is tuple:
        return list(obj)
    else:
        return [obj]


def make_utc_datetime(input_dt: str or datetime or np.float64 or float) -> datetime:
    if type(input_dt) in (np.float64, float):
        return datetime.utcfromtimestamp(input_dt)
    if type(input_dt) is str:
        input_dt = parse(input_dt)
    return input_dt.replace(tzinfo=timezone.utc)


def mkdir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def deprecation(message):
    warnings.warn(message, DeprecationWarning, stacklevel=2)


def all_kwargs(**kwargs):
    return kwargs


def all_of_type(collection, expected_type):
    return all(map(lambda x: type(x) is expected_type, collection))
