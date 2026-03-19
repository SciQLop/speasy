import io
import json
from typing import Optional, Union

from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.bundled_codecs.hapi.writer import save_hapi
from speasy.core.codecs.codec_interface import Buffer

def _to_binary(hapi_file: HapiFile, dest:io.IOBase, with_headers=True) -> bool:
    np_start_date = hapi_file.time_axis[0]
    np_stop_date = hapi_file.time_axis[-1]
    start_date = np_start_date.astype("datetime64[us]").astype("O")
    stop_date = np_stop_date.astype("datetime64[us]").astype("O")
    if with_headers:
        headers = {
            "HAPI": "3.2",
            "startDate": start_date.isoformat() + "Z",
            "stopDate": stop_date.isoformat() + "Z",
            "format": "binary",
            "status": {"code": 1200, "message": "OK request successful"},
            "parameters": [column.meta for column in hapi_file.parameters],
        }
        dest.write(("#" + json.dumps(headers) + "\n").encode("utf-8"))

    n = len(hapi_file.parameters[0].values)

    for i in range(n):
        for p in hapi_file.parameters:
            if p.meta["type"] == "isotime":
                s = p.values[i].astype("datetime64[ms]").astype(str) + "Z"
                dest.write(s.encode())
            elif p.meta["type"] == "double":
                dest.write(p.values[i].astype("<f8").tobytes())
            elif p.meta["type"] == "integer":
                dest.write(p.values[i].astype("<i4").tobytes())

    return True


def save_hapi_binary(
    hapi_file: HapiFile,
    file: Optional[Union[str, io.IOBase]] = None,
    with_headers: bool = True,
) -> Union[bool, Buffer]:
    return save_hapi(hapi_file, file, _to_binary, with_headers=with_headers)
