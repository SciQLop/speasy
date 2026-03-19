

import io
from typing import Optional, Union

from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.bundled_codecs.hapi.writer import save_hapi
from speasy.core.codecs.codec_interface import Buffer

def _to_binary(hapi_file: HapiFile, dest:io.IOBase, with_headers=True) -> bool:
    return True

def save_hapi_binary(
    hapi_file: HapiFile,
    file: Optional[Union[str, io.IOBase]] = None,
    with_headers: bool = True,
) -> Union[bool, Buffer]:
    return save_hapi(hapi_file, file, _to_binary, with_headers=with_headers)

