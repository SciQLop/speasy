from typing import Union
import datetime
import dateutil
from packaging.version import Version, parse, InvalidVersion


def str_to_version(v: str):
    try:
        v = parse(v)
    except InvalidVersion:
        try:
            v = dateutil.parser.parse(v)
        except ValueError:
            v = None
    return v


def version_to_str(v: Union[Version, datetime.datetime]):
    if type(v) is Version:
        return str(v)
    elif type(v) is datetime.datetime:
        return v.isoformat()
