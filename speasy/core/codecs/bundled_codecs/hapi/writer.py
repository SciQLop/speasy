import io
from typing import IO, Any, Dict, Optional, Union, Callable


from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.codec_interface import Buffer
from speasy.core.codecs.bundled_codecs.hapi.isotime import format_isotime


def make_headers(hapi_file: HapiFile, fmt: str) -> Dict[str, Any]:
    time_axis = hapi_file.time_axis
    if len(time_axis) == 0:
        # startDate/stopDate describe the data here, and there is none to describe.
        return {
            "HAPI": "3.2",
            "format": fmt,
            "status": {"code": 1201, "message": "OK - no data for time range"},
            "parameters": [p.meta for p in hapi_file.parameters],
        }
    length = hapi_file.time_axis_meta["length"]
    start_date, stop_date = format_isotime(time_axis[[0, -1]], length)
    return {
        "HAPI": "3.2",
        "startDate": str(start_date),
        "stopDate": str(stop_date),
        "format": fmt,
        "status": {"code": 1200, "message": "OK request successful"},
        "parameters": [p.meta for p in hapi_file.parameters],
    }

def save_hapi(
    hapi_file: HapiFile,
    file: Optional[Union[str, io.IOBase]],
    to_func: Optional[Callable[[HapiFile, IO[bytes], bool], bool]], 
    mode: str = "wb",
    with_headers: bool = True
) -> Union[bool, Buffer]:

    if to_func is None:
        raise ValueError("to_func must be provided and cannot be None")

    if isinstance(file, str):
        with open(file, mode) as f:
            return to_func(hapi_file, f, with_headers)

    elif hasattr(file, "write"):
        return to_func(hapi_file, file, with_headers)

    elif file is None:
        buff = io.BytesIO()
        to_func(hapi_file, buff, with_headers)
        return buff.getvalue()

    raise ValueError("Invalid file type")
