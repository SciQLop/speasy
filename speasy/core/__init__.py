"""
.. testsetup:: *

   from speasy.core import *
   import numpy as np
"""

import os
import warnings
from tqdm.auto import tqdm

from .time import make_utc_datetime, make_utc_datetime64, datetime64_to_epoch, epoch_to_datetime64, EnsureUTCDateTime
from .typing import AnyDateTimeType, all_of_type, is_collection, listify
from .algorithms import pack_kwargs, AllowedKwargs, fix_name, randomized_map


def deprecation(message: str) -> None:
    """Shows a deprecation warning.

    Parameters
    ----------
    message: str
        Custom message to show
    """

    warnings.warn(message, DeprecationWarning, stacklevel=2)


def mkdir(directory: str) -> None:
    """Creates directory and parents if they do not exist

    Parameters
    ----------
    directory: str
        Path to create
    """
    os.makedirs(directory, exist_ok=True)


def progress_bar(leave=True, progress=False, desc=None, **kwargs):
    if not progress:
        return lambda x: x
    else:
        return lambda x: tqdm(x, leave=leave, desc=desc)
