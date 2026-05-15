import io
from collections.abc import Callable
from typing import IO

from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.codec_interface import Buffer


def save_hapi(
    hapi_file: HapiFile,
    file: str | io.IOBase | None,
    to_func: Callable[[HapiFile, IO[bytes], bool], bool] | None, 
    mode: str = "wb",
    with_headers: bool = True
) -> bool | Buffer:

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
