
from ast import Tuple
import io
import json
from typing import Any, Dict

import pandas as pd


def _extract_headers(file: io.IOBase) -> Dict[str, Any]:
    header_line = file.readline()
    assert header_line.startswith(b"#")
    headers = json.loads(header_line[1:].decode("utf-8"))
    return headers


# def _parse_hapi_binary(file: io.IOBase) -> Tuple[pd.DataFrame, Dict[str, Any]]:
#     headers, raw_data = _extract_headers(file)
#     assert headers["parameters"][0]["type"] == "isotime"
#     data = _extract_data(file)
#     return data, headers

