import io
from typing import IO, Optional, Union, Callable


from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.codec_interface import Buffer

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
