"""Decoders turning bucket waveform CDF layouts (one record holds N samples) into flat 1D time series."""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pycdfpp

from speasy.core.data_containers import fill_value_mask
from speasy.core.codecs.bundled_codecs.istp import _fix_attributes_types
from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer


def _time_values(variable: pycdfpp.Variable) -> np.ndarray:
    return pycdfpp.to_datetime64(variable)


def _attributes(variable: pycdfpp.Variable) -> dict:
    return _fix_attributes_types({name: variable.attributes[name][0] for name in variable.attributes})


def _fill_to_nan(values: np.ndarray, meta: dict) -> np.ndarray:
    as_float = values.astype(values.dtype if values.dtype.kind == 'f' else np.float64)
    mask = fill_value_mask(values, meta)
    return as_float if mask is None else np.where(mask, np.nan, as_float)


def _samples_first(values: np.ndarray, sample_axis: int) -> np.ndarray:
    """(n, ..., N, ...) -> (n*N, ...): the sample axis is merged into the record axis."""
    moved = np.moveaxis(values, sample_axis, 1)
    return moved.reshape(-1, *moved.shape[2:])


def _labels(cdf: pycdfpp.CDF, variable: pycdfpp.Variable, width: int) -> list:
    pointer = variable.attributes['LABL_PTR_1'][0] if 'LABL_PTR_1' in variable.attributes else ''
    labels = cdf[pointer].values_encoded.ravel().tolist() if pointer in cdf else []
    return labels if len(labels) == width else [f"component_{i}" for i in range(width)]


def _check_increasing(time: np.ndarray, variable: str):
    if np.any(np.diff(time) <= np.timedelta64(0, 'ns')):
        raise ValueError(f"The flattened time axis of {variable} is not increasing: buckets overlap or are out of "
                         f"order, this layout can't be decoded as a single time series")


def _build(cdf: pycdfpp.CDF, name: str, times: np.ndarray, sample_axis: int, records=slice(None),
           valid=None) -> Optional[SpeasyVariable]:
    """times is (n, N), one row per kept record, `records` selects those records in the data variable,
    `valid` optionally selects samples in the flattened series."""
    variable = cdf[name]
    values = _samples_first(variable.values[records], sample_axis)
    time = times.reshape(-1)
    if valid is not None:
        values, time = values[valid], time[valid]
    if values.shape[0] == 0:
        return None
    _check_increasing(time, name)
    meta = _attributes(variable)
    values = _fill_to_nan(values, meta)
    columns = _labels(cdf, variable, 1 if values.ndim == 1 else values.shape[1])
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                          values=DataContainer(values=values, meta=meta, name=name),
                          columns=columns)


def _offsets_as_timedelta(offsets: np.ndarray, ns_per_unit: float) -> np.ndarray:
    return np.rint(offsets * ns_per_unit).astype('int64').astype('timedelta64[ns]')


def _valid_time_mask(variable: pycdfpp.Variable, times: np.ndarray) -> np.ndarray:
    """Padding samples carry an undeclared sentinel (PSP TDS uses -999999999), outside VALIDMIN/VALIDMAX."""
    mask = np.ones(times.shape, dtype=bool)
    if 'VALIDMIN' in variable.attributes:
        mask &= times >= _time_values(variable.attributes['VALIDMIN'][0])[0]
    if 'VALIDMAX' in variable.attributes:
        mask &= times <= _time_values(variable.attributes['VALIDMAX'][0])[0]
    return mask


@dataclass(frozen=True)
class TimeMatrix:
    """Every sample has its own timestamp, stored in a 2D TT2000 variable shaped like the data.
    Samples whose timestamp is outside the time variable's VALIDMIN/VALIDMAX are padding and dropped."""
    time: str

    def decode(self, cdf: pycdfpp.CDF, variable: str) -> Optional[SpeasyVariable]:
        times = _time_values(cdf[self.time])
        valid = _valid_time_mask(cdf[self.time], times.reshape(-1))
        return _build(cdf, variable, times, sample_axis=1, valid=valid)


@dataclass(frozen=True)
class EpochPlusOffsets:
    """sample time = record epoch + offset, offsets are (1, N) or (n, N) in units of `ns_per_unit` nanoseconds."""
    offsets: str
    ns_per_unit: float
    sample_axis: int = 1
    epoch: str = "Epoch"

    def decode(self, cdf: pycdfpp.CDF, variable: str) -> Optional[SpeasyVariable]:
        offsets = _offsets_as_timedelta(cdf[self.offsets].values, self.ns_per_unit)
        times = _time_values(cdf[self.epoch]).reshape(-1, 1) + offsets
        return _build(cdf, variable, times, self.sample_axis)


@dataclass(frozen=True)
class EpochPlusSamplingRate:
    """Only records sampled at `rate_hz` are kept, sample k of a record is at epoch + k / rate_hz."""
    rate: str
    rate_hz: float
    sample_axis: int = 1
    epoch: str = "Epoch"

    def decode(self, cdf: pycdfpp.CDF, variable: str) -> Optional[SpeasyVariable]:
        keep = cdf[self.rate].values.reshape(-1) == self.rate_hz
        n_samples = cdf[variable].shape[self.sample_axis]
        offsets = _offsets_as_timedelta(np.arange(n_samples), 1e9 / self.rate_hz)
        times = _time_values(cdf[self.epoch]).reshape(-1)[keep].reshape(-1, 1) + offsets
        return _build(cdf, variable, times, self.sample_axis, records=keep)
