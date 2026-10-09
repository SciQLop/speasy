import io
from typing import IO, Any, Dict, Optional, Union, Callable

import numpy as np

from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.codec_interface import Buffer
from speasy.core.codecs.bundled_codecs.hapi.isotime import format_isotime
from speasy.core.time import make_utc_datetime64
from speasy.core.typing import AnyDateTimeType


def _dataset_range(time_axis: np.ndarray, start_date: Optional[AnyDateTimeType],
                   stop_date: Optional[AnyDateTimeType]) -> np.ndarray:
    # HAPI's startDate/stopDate are required and span the whole dataset, not only the records written,
    # so they default to the records' own span and must be given when there are no records.
    if (start_date is None) != (stop_date is None):
        raise ValueError("start_date and stop_date go together, pass both or neither")
    if start_date is None:
        if len(time_axis) == 0:
            raise ValueError("A HAPI header needs startDate and stopDate, which an empty variable can't provide: "
                             "pass start_date and stop_date (the dataset's time range), or with_headers=False")
        return np.array([time_axis.min(), time_axis.max()])
    dataset_range = np.array([make_utc_datetime64(start_date), make_utc_datetime64(stop_date)], dtype="datetime64[ns]")
    if dataset_range[0] > dataset_range[1]:
        raise ValueError(f"start_date {start_date} is after stop_date {stop_date}")
    if len(time_axis) and (time_axis.min() < dataset_range[0] or time_axis.max() > dataset_range[1]):
        raise ValueError(f"Records span {time_axis.min()} to {time_axis.max()}, "
                         f"outside the dataset range {start_date} to {stop_date}")
    return dataset_range


def make_headers(hapi_file: HapiFile, fmt: str, start_date: Optional[AnyDateTimeType] = None,
                 stop_date: Optional[AnyDateTimeType] = None) -> Dict[str, Any]:
    time_axis = hapi_file.time_axis
    length = hapi_file.time_axis_meta["length"]
    start, stop = format_isotime(_dataset_range(time_axis, start_date, stop_date), length)
    if len(time_axis) == 0:
        status = {"code": 1201, "message": "OK - no data for time range"}
    else:
        status = {"code": 1200, "message": "OK request successful"}
    return {
        "HAPI": "3.2",
        "startDate": str(start),
        "stopDate": str(stop),
        "format": fmt,
        "status": status,
        "parameters": [p.meta for p in hapi_file.parameters],
    }


def save_hapi(
    hapi_file: HapiFile,
    file: Optional[Union[str, io.IOBase]],
    to_func: Optional[Callable[[HapiFile, IO[bytes], Optional[Dict[str, Any]]], bool]],
    headers: Optional[Dict[str, Any]] = None,
    mode: str = "wb",
) -> Union[bool, Buffer]:

    if to_func is None:
        raise ValueError("to_func must be provided and cannot be None")

    if isinstance(file, str):
        with open(file, mode) as f:
            return to_func(hapi_file, f, headers)

    elif hasattr(file, "write"):
        return to_func(hapi_file, file, headers)

    elif file is None:
        buff = io.BytesIO()
        to_func(hapi_file, buff, headers)
        return buff.getvalue()

    raise ValueError("Invalid file type")
