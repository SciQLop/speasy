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


def _interpolate(var: SpeasyVariable, ref_time: np.ndarray) -> SpeasyVariable:
    res = SpeasyVariable.reserve_like(var, length=len(ref_time))
    res.time[:] = ref_time
    var_epoch = datetime64_to_epoch(var.time)
    res_epoch = datetime64_to_epoch(res.time)
    for col in range(var.values.shape[1]):
        res.values[:, col] = np.interp(res_epoch, var_epoch, var.values[:, col])
    return res


def resample(var: SpeasyVariable, new_dt: Union[float, np.timedelta64]) -> SpeasyVariable:
    """Resample a variable to a new time step. The time vector will be generated from the start and stop times of the
    input variable.

    Parameters
    ----------
    var: SpeasyVariable
        The variable to resample
    new_dt: float or np.timedelta64
        The new time step in seconds or as a numpy timedelta64

    Returns
    -------
    SpeasyVariable
        The resampled variable
    """
    time = generate_time_vector(var.time[0], var.time[-1] + np.timedelta64(1, 'ns'), new_dt)
    return _interpolate(var, time)


def interpolate(var: SpeasyVariable, ref_time: Optional[np.ndarray] = None,
                ref_variable: Optional[SpeasyVariable] = None) -> SpeasyVariable:
    """Interpolate a variable to a new time vector or to the time vector of a reference variable. Either ref_time or
    ref_variable must be provided. If both are provided, ref_time will be used. If neither are provided, an error will
    be raised.

    Parameters
    ----------
    var: SpeasyVariable
        The variable to interpolate
    ref_time: np.ndarray or None
        The reference time vector to interpolate to (optional)
    ref_variable: SpeasyVariable or None
        The reference variable to interpolate to (optional)

    Returns
    -------
    SpeasyVariable
        The interpolated variable
    """
    if ref_time is None and ref_variable is None:
        raise ValueError("Either ref_time or ref_variable must be provided")
    if ref_time is None and ref_variable is not None:
        ref_time = ref_variable .time
    return _interpolate(var, ref_time)
