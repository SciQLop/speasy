import io
import json
from typing import IO, Any, Dict, Optional, Union

import numpy as np

from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.bundled_codecs.hapi.writer import save_hapi, make_headers
from speasy.core.codecs.bundled_codecs.hapi.isotime import format_isotime
from speasy.core.codecs.codec_interface import Buffer
from speasy.core.typing import AnyDateTimeType

def _base_np_type(p):
    """
    Returns the base NumPy type string for a HAPI parameter, ignoring shape.
    For isotime, the byte length is the one declared in the parameter's metadata.
    """
    if p.meta["type"] == "isotime":
        return f"S{p.meta['length']}"
    elif p.meta["type"] == "double":
        return "<f8"
    else:
        return "<i4"


def _get_np_type(p):
    """
    Returns the full NumPy type descriptor for a HAPI parameter.

    if Scalar then -> base type string.
    if Multi-dimensional then -> (base_type, shape) tuple.

    Shape is p.values.shape[1:] — all dimensions except the time axis.
    """
    base = _base_np_type(p)
    shape = p.values.shape[1:]
    return (base, shape) if shape else base


def _to_binary(hapi_file: HapiFile, dest: IO[bytes], headers: Optional[Dict[str, Any]]) -> bool:

    if headers is not None:
        dest.write(("#" + json.dumps(headers) + "\n").encode("utf-8"))

    # build the dtype structure: set np type by parameter name
    dtype = np.dtype([(p.name, _get_np_type(p)) for p in hapi_file.parameters])

    # build empty np.ndarray structure
    n = len(hapi_file.parameters[0].values)
    out = np.empty(n, dtype=dtype)

    # fill in np.ndarray structure values by parameter name
    for p in hapi_file.parameters:
        np_type = _base_np_type(p)
        if p.meta["type"] == "isotime":
            out[p.name] = format_isotime(p.values, p.meta["length"]).astype(np_type)
        else:
            out[p.name] = p.values.astype(np_type)

    dest.write(out.tobytes())
    return True


def save_hapi_binary(
    hapi_file: HapiFile,
    file: Optional[Union[str, io.IOBase]] = None,
    with_headers: bool = True,
    start_date: Optional[AnyDateTimeType] = None,
    stop_date: Optional[AnyDateTimeType] = None,
) -> Union[bool, Buffer]:
    """start_date and stop_date are the dataset's time range for the header (HAPI's startDate/stopDate),
    the span of the records written by default; an empty file with a header needs them."""
    headers = make_headers(hapi_file, "binary", start_date, stop_date) if with_headers else None
    return save_hapi(hapi_file, file, _to_binary, headers=headers)
