import io
import logging
from typing import Any

import numpy as np
import pandas as pds

from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.bundled_codecs.hapi.reader import _load_hapi
from speasy.core.codecs.codec_interface import Buffer

log = logging.getLogger(__name__)


def _extract_data_csv(file: io.IOBase, headers: dict[str, Any]) -> pds.DataFrame:
    data = io.BytesIO(file.read())
    return pds.read_csv(data, comment='#', sep=',', header=None, skiprows=0, parse_dates=[0], index_col=0)



def load_hapi_csv(file: Buffer | str | io.IOBase) -> HapiFile | None:
    data, headers = _load_hapi(file, _extract_data_csv)
    hapi_csv_file = HapiFile()
    if data is not None and headers is not None:
        time_header = headers["parameters"][0]
        assert time_header["type"] == "isotime"
        hapi_csv_file.create_parameter(data.index.to_numpy(dtype="datetime64[ns]"),
                                       meta=time_header)
        column_offset = 0
        for i, param_meta in enumerate(headers["parameters"][1:]):
            shape = param_meta.get("size", [1])
            flatten_shape = np.prod(shape)
            hapi_csv_file.create_parameter(data.iloc[:, column_offset:column_offset + flatten_shape].to_numpy().reshape(
                [len(data.index)] + shape), meta=param_meta)
            column_offset += flatten_shape
        return hapi_csv_file
    return None
