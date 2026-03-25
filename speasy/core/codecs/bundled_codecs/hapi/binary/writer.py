import io
import json
from typing import Optional, Union

import numpy as np

from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.bundled_codecs.hapi.writer import save_hapi
from speasy.core.codecs.codec_interface import Buffer

def _base_np_type(p):
    """
    Returns the base NumPy type string for a HAPI parameter, ignoring shape.
    For isotime, computes byte length from actual values (datetime64[ms] + "Z").
    """
    if p.meta["type"] == "isotime":
        length = len(p.values[0].astype("datetime64[ms]").astype(str)) + 1
        return f"S{length}"
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


def _to_binary(hapi_file: HapiFile, dest:io.IOBase, with_headers=True) -> bool:

    if with_headers:
        np_start_date = hapi_file.time_axis[0].astype("datetime64[us]").astype("O")
        np_stop_date = hapi_file.time_axis[-1].astype("datetime64[us]").astype("O")
        headers = {
            "HAPI": "3.2",
            "startDate": np_start_date.isoformat() + "Z",
            "stopDate": np_stop_date.isoformat() + "Z",
            "format": "binary",
            "status": {"code": 1200, "message": "OK request successful"},
            "parameters": [column.meta for column in hapi_file.parameters],
        }
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
            out[p.name] = (p.values.astype("datetime64[ms]").astype(str) + "Z").astype(np_type)
        else:
            out[p.name] = p.values.astype(np_type)

    dest.write(out.tobytes())
    return True


def save_hapi_binary(
    hapi_file: HapiFile,
    file: Optional[Union[str, io.IOBase]] = None,
    with_headers: bool = True,
) -> Union[bool, Buffer]:
    return save_hapi(hapi_file, file, _to_binary, with_headers=with_headers)
