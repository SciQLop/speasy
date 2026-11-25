"""Decoders turning bucket waveform CDF layouts (one record holds N samples) into flat 1D time series."""
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, Union

import numpy as np
import pycdfpp

from speasy.core.data_containers import fill_value_mask
from speasy.core.codecs.bundled_codecs.istp import _fix_attributes_types
from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer

log = logging.getLogger(__name__)

_FAR_FUTURE = np.datetime64(np.iinfo(np.int64).max, 'ns')
_FAR_PAST = np.datetime64(np.iinfo(np.int64).min + 1, 'ns')


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


def _not_cut_by_next_bucket(times: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Same rule as speasy's `merge`: where a bucket's tail overlaps the next one, the next bucket wins.
    Only a true tail overlap is cut: the next bucket starts after this one and ends no earlier. Anything else
    (out of order, nested, same start) is left alone so `_check_increasing` rejects it.
    `times` and `valid` are (n, N); a bucket without valid sample never cuts and is never a cutter."""
    firsts = np.where(valid, times, _FAR_FUTURE).min(axis=1)
    lasts = np.where(valid, times, _FAR_PAST).max(axis=1)
    is_tail_overlap = (firsts[1:] > firsts[:-1]) & (lasts[1:] >= lasts[:-1])
    cuts = np.append(np.where(is_tail_overlap, firsts[1:], _FAR_FUTURE), _FAR_FUTURE)
    return times < cuts.reshape(-1, 1)


def _kept_samples(times: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Flat mask of the samples to keep: valid ones that the next bucket doesn't overlap."""
    return (valid & _not_cut_by_next_bucket(times, valid)).reshape(-1)


def _to_variable(cdf: pycdfpp.CDF, name: str, time: np.ndarray, values: np.ndarray) -> SpeasyVariable:
    _check_increasing(time, name)
    variable = cdf[name]
    meta = _attributes(variable)
    values = _fill_to_nan(values, meta)
    columns = _labels(cdf, variable, 1 if values.ndim == 1 else values.shape[1])
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                          values=DataContainer(values=values, meta=meta, name=name),
                          columns=columns)


def _build(cdf: pycdfpp.CDF, name: str, times: np.ndarray, values: np.ndarray,
           valid: Optional[np.ndarray] = None) -> Optional[SpeasyVariable]:
    """`times` is (n, N), one timestamp per sample; `values` is already flattened to (n*N, ...);
    `valid` is an optional (n, N) mask of the samples to keep."""
    if values.shape[0] == 0:
        return None
    kept = _kept_samples(times, np.ones(times.shape, dtype=bool) if valid is None else valid)
    if not kept.any():
        return None
    return _to_variable(cdf, name, times.reshape(-1)[kept], values[kept])


def _records(n: int) -> str:
    return f"{n} record" if n == 1 else f"{n} records"


def _same_records(source: str, variable: str, data: np.ndarray, **time_side: np.ndarray) -> Tuple[np.ndarray, ...]:
    """``data`` and the per-record time-side arrays cut to the records present in all of them: record i of each
    describes the same bucket, but a file can hold more of one than of the other
    (psp_fld_l2_tds_wf_20190415_v00.cdf has 2 records of sample times for 1 record of data)."""
    counts = {name: len(array) for name, array in time_side.items()}
    kept = min(len(data), *counts.values())
    if any(count != len(data) for count in counts.values()):
        others = ', '.join(f"{name!r} has {_records(count)}" for name, count in counts.items())
        log.warning(f"{source or 'CDF file'}: {variable!r} has {_records(len(data))} but {others}: keeping the "
                    f"first {_records(kept)}")
    return (data[:kept],) + tuple(array[:kept] for array in time_side.values())


def _offsets_as_timedelta(offsets: np.ndarray, ns_per_unit: float) -> np.ndarray:
    return np.rint(offsets * ns_per_unit).astype('int64').astype('timedelta64[ns]')


def _not_padding_mask(variable: pycdfpp.Variable, times: np.ndarray) -> np.ndarray:
    """Padding samples carry an undeclared sentinel (PSP TDS uses -999999999), below VALIDMIN.
    VALIDMAX is deliberately ignored: a too early VALIDMAX would silently drop real data."""
    if 'VALIDMIN' not in variable.attributes:
        return np.ones(times.shape, dtype=bool)
    return times >= _time_values(variable.attributes['VALIDMIN'][0])[0]


@dataclass(frozen=True)
class TimeMatrix:
    """Every sample has its own timestamp, stored in a 2D TT2000 variable shaped like the data.
    Samples whose timestamp is below the time variable's VALIDMIN are padding and dropped."""
    time: str

    def decode(self, cdf: pycdfpp.CDF, variable: str, source: str = "") -> Optional[SpeasyVariable]:
        values, times = _same_records(source, variable, cdf[variable].values,
                                      **{self.time: _time_values(cdf[self.time])})
        valid = _not_padding_mask(cdf[self.time], times)
        return _build(cdf, variable, times, _samples_first(values, 1), valid)


@dataclass(frozen=True)
class EpochPlusOffsets:
    """sample time = record epoch + offset, offsets are (1, N) or (n, N) in units of `ns_per_unit` nanoseconds."""
    offsets: str
    ns_per_unit: float
    sample_axis: int = 1
    epoch: str = "Epoch"

    def decode(self, cdf: pycdfpp.CDF, variable: str, source: str = "") -> Optional[SpeasyVariable]:
        offsets = cdf[self.offsets].values
        per_record = {self.epoch: _time_values(cdf[self.epoch]).reshape(-1)}
        if offsets.shape[0] > 1:  # (1, N) offsets apply to every record
            per_record[self.offsets] = offsets
        values, epoch, *per_record_offsets = _same_records(source, variable, cdf[variable].values, **per_record)
        offsets = _offsets_as_timedelta(per_record_offsets[0] if per_record_offsets else offsets, self.ns_per_unit)
        return _build(cdf, variable, epoch.reshape(-1, 1) + offsets, _samples_first(values, self.sample_axis))


@dataclass(frozen=True)
class EpochPlusSamplingRate:
    """Sample k of a record is at epoch + k / rate. With `rate_hz` only records sampled at that rate are kept
    (products split per rate), with None every record is kept and uses its own `rate` value."""
    rate: str
    rate_hz: Optional[float] = None
    sample_axis: int = 1
    epoch: str = "Epoch"

    def decode(self, cdf: pycdfpp.CDF, variable: str, source: str = "") -> Optional[SpeasyVariable]:
        values, epoch, rates = _same_records(source, variable, cdf[variable].values,
                                             **{self.epoch: _time_values(cdf[self.epoch]).reshape(-1),
                                                self.rate: cdf[self.rate].values.reshape(-1)})
        keep = np.ones(rates.shape, dtype=bool) if self.rate_hz is None else rates == self.rate_hz
        periods_ns = 1e9 / rates[keep].astype(np.float64)
        offsets = _offsets_as_timedelta(np.arange(values.shape[self.sample_axis]) * periods_ns.reshape(-1, 1), 1.0)
        times = epoch[keep].reshape(-1, 1) + offsets
        return _build(cdf, variable, times, _samples_first(values[keep], self.sample_axis))


Decoder = Union[TimeMatrix, EpochPlusOffsets, EpochPlusSamplingRate]
