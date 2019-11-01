from packaging import version
import dateutil, datetime
from typing import Union


def str_to_version(v:str):
    try:
        v = version.parse(v)
    except version.InvalidVersion:
        try:
            v = dateutil.parser.parse(v)
        except ValueError:
            v = None
    return v


def version_to_str(v:Union[version.Version,datetime.datetime]):
    if type(v) is version.Version:
        return str(v)
    elif type(v) is datetime.datetime:
        return v.isoformat()

