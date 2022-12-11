from typing import Union
import datetime
import dateutil
from packaging.version import Version, parse, InvalidVersion


def _str_to_version_datetime(v: str) -> datetime.datetime or None:
    try:
        version = dateutil.parser.parse(v)
    except ValueError:
        version = None
    return version


def str_to_version(v: str) -> Version or datetime.datetime or None:
    """Converts given version str representation to a compatible version object

    Parameters
    ----------
    v: str
        version value to convert

    Returns
    -------
    Version or datetime.datetime or None
        a compatible version object or None

    Examples
    --------

    >>> from speasy.core.cache.version import str_to_version
    >>> import datetime
    >>> str_to_version("1.2.3")
    <Version('1.2.3')>
    >>> str_to_version('2010-01-01T00:00:00')
    datetime.datetime(2010, 1, 1, 0, 0)

    See Also
    --------
    version_to_str
    """
    try:
        version = parse(v)
        if "LegacyVersion" in str(type(version)):
            return _str_to_version_datetime(v)
    except InvalidVersion:
        return _str_to_version_datetime(v)
    return version


def version_to_str(v: Union[Version, datetime.datetime]) -> str:
    """Converts given version value to its str representation

    Parameters
    ----------
    v: Version or datetime.datetime
        version value to convert

    Returns
    -------
    str
        string representation of given version

    Examples
    --------

    >>> from speasy.core.cache.version import version_to_str
    >>> from packaging.version import Version
    >>> import datetime
    >>> version_to_str(Version("1.2.3"))
    '1.2.3'
    >>> version_to_str(datetime.datetime(2010, 1, 1))
    '2010-01-01T00:00:00'

    See Also
    --------
    str_to_version
    """
    if type(v) is Version:
        return str(v)
    elif type(v) is datetime.datetime:
        return v.isoformat()
