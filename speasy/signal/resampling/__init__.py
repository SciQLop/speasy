import numpy
from scipy import signal
from typing import Callable, Optional, Union
from speasy.products import SpeasyVariable
import numpy as np
from speasy.core import AnyDateTimeType, make_utc_datetime64, datetime64_to_epoch


def _dt_to_ns(dt: float) -> np.timedelta64:
    return np.timedelta64(int(dt * 1e9), 'ns')


def generate_time_vector(start: AnyDateTimeType, stop: AnyDateTimeType,
                         dt: Union[float, numpy.timedelta64]) -> np.ndarray:
    """Generate a time vector given a start, stop and time step. The time vector will be generated in UTC time zone. The
    time step is in seconds.

    Parameters
    ----------
    start: float or datetime or np.datetime64
        The start time
    stop: float or datetime or np.datetime64
        The stop time
    dt: float or np.timedelta64
        The time step in seconds or as a numpy timedelta64

    Returns
    -------
    np.ndarray
        The time vector as a numpy array of datetime64[ns]
    """
    if type(dt) in (float, int):
        dt = _dt_to_ns(dt)
    return np.arange(make_utc_datetime64(start), make_utc_datetime64(stop), dt, dtype='datetime64[ns]')


class _NumpyInterpolator:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __call__(self, new_x):
        return np.interp(new_x, self.x, self.y)


def _interpolate(var: SpeasyVariable, ref_time: np.ndarray, interpolate_callback: Optional[Callable] = None, *args,
                 **kwargs) -> SpeasyVariable:
    res = SpeasyVariable.reserve_like(var, length=len(ref_time))
    res.time[:] = ref_time
    var_epoch = datetime64_to_epoch(var.time)
    res_epoch = datetime64_to_epoch(res.time)
    for col in range(var.values.shape[1]):
        if interpolate_callback is None:
            interpolator = _NumpyInterpolator(var_epoch, var.values[:, col])
        else:
            interpolator = interpolate_callback(var_epoch, var.values[:, col], *args, **kwargs)
        res.values[:, col] = interpolator(res_epoch)
    return res


def resample(var: SpeasyVariable, new_dt: Union[float, np.timedelta64], interpolate_callback: Optional[Callable] = None,
             *args, **kwargs) -> SpeasyVariable:
    """Resample a variable to a new time step. The time vector will be generated from the start and stop times of the
    input variable. Uses :func:`numpy.interp` to do the resampling by default.

    Parameters
    ----------
    var: SpeasyVariable
        The variable to resample
    new_dt: float or np.timedelta64
        The new time step in seconds or as a numpy timedelta64
    interpolate_callback: Callable or None
        The interpolation function to use, defaults to :func:`numpy.interp`

    Returns
    -------
    SpeasyVariable
        The resampled variable
    """
    time = generate_time_vector(var.time[0], var.time[-1] + np.timedelta64(1, 'ns'), new_dt)
    return _interpolate(var, time, interpolate_callback, *args, **kwargs)


def interpolate(var: SpeasyVariable, ref: Union[np.ndarray, SpeasyVariable],
                interpolate_callback: Optional[Callable] = None,
                *args, **kwargs) -> SpeasyVariable:
    """Interpolate a variable to a new time vector or to the time vector of a reference variable. Uses :func:`numpy.interp` to do the resampling by default.

    Parameters
    ----------
    var: SpeasyVariable
        The variable to interpolate to a new time vector.
    ref: np.ndarray or SpeasyVariable
        The reference time vector or variable to interpolate to.
    interpolate_callback: Callable or None
        The interpolation function to use, defaults to :func:`numpy.interp`


    Returns
    -------
    SpeasyVariable
        The interpolated variable
    """
    if isinstance(ref, SpeasyVariable):
        ref_time = ref.time
    elif isinstance(ref, np.ndarray) and ref.dtype == np.dtype('datetime64[ns]'):
        ref_time = ref
    else:
        raise ValueError("Invalid reference time vector, must be a numpy array of datetime64[ns] or a SpeasyVariable.")
    return _interpolate(var, ref_time, interpolate_callback, *args, **kwargs)
