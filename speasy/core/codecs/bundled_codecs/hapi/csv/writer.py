from typing import IO, Any, Dict, Union, Optional
import io
from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.bundled_codecs.hapi.writer import save_hapi, make_headers
from speasy.core.codecs.bundled_codecs.hapi.isotime import format_isotime
from speasy.core.codecs.codec_interface import Buffer
from speasy.core.typing import AnyDateTimeType
import json
import numpy as np
import pandas as pds


def _to_csv(hapi_file: HapiFile, dest: IO[bytes], headers: Optional[Dict[str, Any]]) -> bool:
    if headers is not None:
        dest.write(("#" + json.dumps(headers) + "\n").encode("utf-8"))

    data = {}
    for param in hapi_file.parameters:
        vals = param.values
        if param.meta["type"] == "isotime":
            data[param.name] = format_isotime(vals, param.meta["length"])
        elif vals.ndim == 1:
            data[param.name] = vals
        else:
            # HAPI unwinds arrays with the last index fastest, as numpy's C order does
            vals = vals.reshape(len(vals), int(np.prod(vals.shape[1:])))
            for i in range(vals.shape[1]):
                data[f"{param.name}_{i}"] = vals[:, i]

    df = pds.DataFrame(data)
    # pandas writes NaN as an empty field by default, which HAPI clients can't parse as a double
    df.to_csv(dest, index=False, header=False, float_format='%.7g', na_rep='NaN')
    return True


def save_hapi_csv(
    hapi_file: HapiFile,
    file: Optional[Union[str, io.IOBase]] = None,
    with_headers: bool = True,
    start_date: Optional[AnyDateTimeType] = None,
    stop_date: Optional[AnyDateTimeType] = None,
) -> Union[bool, Buffer]:
    """start_date and stop_date are the dataset's time range for the header (HAPI's startDate/stopDate),
    the span of the records written by default; an empty file with a header needs them."""
    headers = make_headers(hapi_file, "csv", start_date, stop_date) if with_headers else None
    return save_hapi(hapi_file, file, _to_csv, headers=headers)
