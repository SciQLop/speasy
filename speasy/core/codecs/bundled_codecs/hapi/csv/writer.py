from typing import IO, Union, Optional
import io
from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.bundled_codecs.hapi.writer import save_hapi, make_headers
from speasy.core.codecs.bundled_codecs.hapi.isotime import format_isotime
from speasy.core.codecs.codec_interface import Buffer
import json
import pandas as pds


def _to_csv(hapi_file: HapiFile, dest:IO[bytes], with_headers=True) -> bool:
    if with_headers:
        headers = make_headers(hapi_file, "csv")
        dest.write(("#" + json.dumps(headers) + "\n").encode("utf-8"))

    data = {}
    for param in hapi_file.parameters:
        vals = param.values
        if param.meta["type"] == "isotime":
            data[param.name] = format_isotime(vals, param.meta["length"])
        elif vals.ndim == 1:
            data[param.name] = vals
        else:
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
) -> Union[bool, Buffer]:
    return save_hapi(hapi_file, file, _to_csv, with_headers=with_headers)
