from scipy import signal
from typing import Callable, Union, Collection
from speasy.products import SpeasyVariable
import numpy as np


def _apply_filter(filter_function: Callable, sos: np.ndarray, var: SpeasyVariable) -> SpeasyVariable:
    res = np.empty_like(var)
    res.values[:] = filter_function(sos=sos, x=var.values, axis=0)
    return res


def apply_sos_filter(sos: np.ndarray, filter_function: Callable,
                     var: Union[SpeasyVariable, Collection[SpeasyVariable]]) -> Union[
    SpeasyVariable, Collection[SpeasyVariable]]:
    """Apply an IIR filter to the variable(s) using the given filter function. This function just applies the filter to the
    values of the variable without any resampling, it assumes that the variable has a regular time axis.

    Parameters
    ----------
    sos: np.ndarray
        Second-order sections representation of the filter, as returned by :func:`scipy.signal.iirfilter` with `output='sos'` for example.
    filter_function: Callable
        The filter function to use (e.g. :func:`scipy.signal.sosfiltfilt`)
    var: SpeasyVariable or Collection[SpeasyVariable]
        The variable(s) to filter

    Returns
    -------
    SpeasyVariable or Collection[SpeasyVariable]
        The filtered variable(s)

    Notes
    -----
    It only supports 1D variables.
    """

    if isinstance(var, SpeasyVariable):
        return _apply_filter(filter_function, sos, var)
    else:
        return [_apply_filter(filter_function, sos, v) for v in var]


def sosfiltfilt(sos: np.ndarray, var: Union[SpeasyVariable, Collection[SpeasyVariable]]) -> Union[
    SpeasyVariable, Collection[SpeasyVariable]]:
    """Apply an IIR filter to the variable(s) using :func:`scipy.signal.sosfiltfilt`. This function just applies the filter to
    the values of the variable without any resampling, it assumes that the variable has a regular time axis.

    Parameters
    ----------
    sos: np.ndarray
        Second-order sections representation of the filter
    var: SpeasyVariable or Collection[SpeasyVariable]
        The variable(s) to filter

    Returns
    -------
    SpeasyVariable or Collection[SpeasyVariable]
        The filtered variable(s)

    Notes
    -----
    It only supports 1D variables.
    """
    return apply_sos_filter(sos, signal.sosfiltfilt, var)
