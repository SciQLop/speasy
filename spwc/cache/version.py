from typing import Union
import datetime
import dateutil
from packaging.version import Version, parse, InvalidVersion, LegacyVersion


def str_to_version(v: str):
    version = parse(v)
    if type(version) is LegacyVersion:
        try:
            version = dateutil.parser.parse(v)
        except ValueError:
            version = None
    return version


def version_to_str(v: Union[Version, datetime.datetime]):
    if type(v) is Version:
        return str(v)
    elif type(v) is datetime.datetime:
        return v.isoformat()
