

import io
import json
from typing import Any, Dict, Optional, Tuple, Union

import pandas as pd

from speasy.core.any_files import any_loc_open
from speasy.core.codecs.codec_interface import Buffer


def _extract_headers(file: io.IOBase) -> Dict[str, Any]:
    file.seek(0)
    header_lines = []
    while True:
        pos = file.tell()
        line = file.readline()
        if not line.startswith(b"#"):
            file.seek(pos)  # set pos to data start
            break
        header_lines.append(line[1:])
    if not header_lines:
        return {}
    return json.loads(b"".join(header_lines).decode("utf-8"))

def _parse_hapi(file: io.IOBase, extract_data_fn ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    headers = _extract_headers(file)
    assert headers["parameters"][0]["type"] == "isotime"
    data = extract_data_fn(file, headers)
    return data, headers


def _load_hapi(file: Union[Buffer, str, io.IOBase], extract_data_fn) -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
    if isinstance(file, str):
        with any_loc_open(file, cache_remote_files=False, mode='rb') as f:
            return _parse_hapi(f, extract_data_fn)
    if isinstance(file, io.IOBase) or hasattr(file, 'read'):
        return _parse_hapi(file, extract_data_fn)
    return None, None
