from typing import Union, Optional
import io
from speasy.core.codecs.codec_interface import Buffer
from .csv_file import HapiCsvFile
import json
import pandas as pds


def _to_csv(hapi_csv_file: HapiCsvFile, dest:io.IOBase, with_headers=True) -> bool:
    if with_headers:
        headers = {
            "HAPI": "3.2",
            "status": {
                "code": 1200,
                "message": "OK request successful"
            },
            "parameters": [column.meta for column in hapi_csv_file.parameters]
        }
        json_str = json.dumps(headers, indent=2, ensure_ascii=False)
        commented = "\n".join("#" + line for line in json_str.splitlines())
        dest.write((commented + "\n").encode("utf-8"))


    data = {}
    for param in hapi_csv_file.parameters:
        vals = param.values
        if vals.ndim == 1:
            data[param.name] = vals
        else:
            for i in range(vals.shape[1]):
                data[f"{param.name}_{i}"] = vals[:, i]

    df = pds.DataFrame(data)
    df.to_csv(dest, index=False, header=False, date_format='%Y-%m-%dT%H:%M:%S.%fZ', float_format='%.3g')
    return True





def save_hapi_csv(hapi_csv_file: HapiCsvFile, file: Optional[Union[str, io.IOBase]] = None) -> Union[bool, Buffer]:
    if type(file) is str:
        with open(file, 'wb') as f:
            return _to_csv(hapi_csv_file, f)
    elif hasattr(file, 'write'):
        return _to_csv(hapi_csv_file, file)
    elif file is None:
        buff = io.BytesIO()
        _to_csv(hapi_csv_file, buff)
        return buff.getvalue()
    raise ValueError("Invalid file type")


