from typing import Union, Optional
import io
from speasy.core.codecs.bundled_codecs.hapi.hapi_file import HapiFile
from speasy.core.codecs.codec_interface import Buffer
import json
import pandas as pds


def _to_csv(hapi_csv_file: HapiFile, dest:io.IOBase, with_headers=True) -> bool:
    np_start_date = hapi_csv_file.time_axis[0]
    np_stop_date = hapi_csv_file.time_axis[-1]
    start_date  = np_start_date.astype("datetime64[us]").astype("O")
    stop_date = np_stop_date.astype("datetime64[us]").astype("O")
    if with_headers:
        headers = {
            "HAPI": "3.2",
            "startDate": start_date.isoformat() + "Z",
            "stopDate": stop_date.isoformat() + "Z",
            "format": "csv",
            "status": {
                "code": 1200,
                "message": "OK request successful"
            },
            "parameters": [column.meta for column in hapi_csv_file.parameters]
        }
        dest.write(("#" + json.dumps(headers) + "\n").encode("utf-8"))

    data = {}
    for param in hapi_csv_file.parameters:
        vals = param.values
        if vals.ndim == 1:
            data[param.name] = vals
        else:
            for i in range(vals.shape[1]):
                data[f"{param.name}_{i}"] = vals[:, i]

    df = pds.DataFrame(data)
    df.to_csv(dest, index=False, header=False, date_format='%Y-%m-%dT%H:%M:%S.%fZ', float_format='%.7g')
    return True


def save_hapi_csv(hapi_csv_file: HapiFile, file: Optional[Union[str, io.IOBase]] = None, with_headers: bool = True) -> Union[bool, Buffer]:
    if type(file) is str:
        with open(file, 'wb') as f:
            return _to_csv(hapi_csv_file, f, with_headers=with_headers)
    elif hasattr(file, 'write'):
        return _to_csv(hapi_csv_file, file, with_headers=with_headers)
    elif file is None:
        buff = io.BytesIO()
        _to_csv(hapi_csv_file, buff, with_headers=with_headers)
        return buff.getvalue()
    raise ValueError("Invalid file type")
