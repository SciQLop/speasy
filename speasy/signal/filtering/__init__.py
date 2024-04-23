from scipy import signal
from typing import Callable
from speasy.products import SpeasyVariable
import numpy as np


def apply_sos_filter(sos: np.ndarray, filter_function: Callable, var: SpeasyVariable) -> SpeasyVariable:
    res = np.empty_like(var)
    res.values[:] = filter_function(sos, var.values, axis=0)
    return res


def sosfiltfilt(sos: np.ndarray, var: SpeasyVariable) -> SpeasyVariable:
    """Apply an IIR filter to the data using :func:`scipy.signal.sosfiltfilt`.

    Parameters
    ----------
    sos: np.ndarray
        Second-order sections representation of the filter
    var: SpeasyVariable
        The variable to filter

    Returns
    -------
    SpeasyVariable
        The filtered variable
    """
    return apply_sos_filter(sos, signal.sosfiltfilt, var)
