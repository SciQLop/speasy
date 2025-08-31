"""uiowa_eph_tool package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import re

from packaging.version import Version
import numpy as np
from urllib.parse import urlencode

from speasy.core import EnsureUTCDateTime, fix_name
from speasy.core.cache import Cacheable, CACHE_ALLOWED_KWARGS
from speasy.core.dataprovider import DataProvider, ParameterRangeCheck, GET_DATA_ALLOWED_KWARGS
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
from speasy.core.requests_scheduling import SplitLargeRequests
from speasy.products.variable import SpeasyVariable, VariableTimeAxis, DataContainer
from ...core import AllowedKwargs, http

log = logging.getLogger(__name__)

# basic translation from https://space.physics.uiowa.edu/~jbg/cas.html
__SUN_COORDINATES__ = {
    "Ecliptic": "ecli",
    "Equatorial": "equa",
}

__PLANET_COORDINATES__ = {
    "Geographic": "geog",
    "Ecliptic": "ecli",
    "Equatorial": "equa"
}

__SATURN_COORDINATES__ = {
    "Geographic": "geog",
    "Ecliptic": "ecli",
    "Equatorial": "equa",
    "KSM": "khsm",
}

__SATELLITE_COORDINATES__ = {
    "Geographic": "geog",
    "Ecliptic": "ecli",
    "Equatorial": "equa",
    "Co-rotational": "crot",
}

__SUN_OBSERVERS__ = {
    "Venus": "venu",
    "Earth": "eart",
    "Jupiter": "jupi",
    "Saturn baricentric": "sat1",
    "Saturn geocentric": "sat2",
    "Voyager 1": "voy1",
    "Voyager 2": "voy2",
    "Galileo": "gali",
    "Ulysses": "ulys",
    "Cassini": "cass",
}

__VENUS_OBSERVERS__ = {
    "Galileo": "gali",
    "Cassini": "cass",
}

__EARTH_OBSERVERS__ = {
    "Voyager 1": "voy1",
    "Voyager 2": "voy2",
    "Galileo": "gali",
    "Ulysses": "ulys",
    "Cassini": "cass",
}

__JUPITER_OBSERVERS__ = {
    "Io": "  io",
    "Europa": "euro",
    "Ganymede": "gany",
    "Callisto": "call",
    "Voyager 1": "voy1",
    "Voyager 2": "voy2",
    "Galileo": "gali",
    "Ulysses": "ulys",
    "Cassini": "cass",
}

__SATURN_OBSERVERS__ = {
    "Mimas": "mima",
    "Enceladus": "ence",
    "Tethys": "teth",
    "Dione": "dion",
    "Rhea": "rhea",
    "Titan": "tita",
    "Hyperion": "hyp",
    "Iapetus": "iape",
    "Phoebe": "phoe",
    "Methone": "meth",
    "Anthe": "anth",
    "Pallene": "pall",
    "Telesto": "tele",
    "Helene": "hele",
    "Voyager 1": "voy1",
    "Voyager 2": "voy2",
    "Ulysses": "ulys",
    "Cassini": "cass",
}

__JUPITER_SATELLITE_OBSERVERS__ = {
    "Voyager 1": "voy1",
    "Voyager 2": "voy2",
    "Galileo": "gali",
    "Cassini": "cass",
    "Jupiter": "jupi",
}

__SATELLITE_SATELLITE_OBSERVERS__ = {
    "Voyager 1": "voy1",
    "Voyager 2": "voy2",
    "Cassini": "cass",
}

__RADIUS_DICT__ = {
    "Sun": 149597871.,
    "Venus": 6051.8,
    "Earth": 6378.14,
    "Jupiter": 71492.,
    "Saturn": 60268.,
    "Io": 1824.4,
    "Europa": 1562.8,
    "Ganymede": 2631.2,
    "Callisto": 2410.3,
    "Mimas": 202.1,
    "Enceladus": 254.0,
    "Tethys": 535.8,
    "Dione": 562.4,
    "Rhea": 764.8,
    "Titan": 2575.,
    "Hyperion": 147.,
    "Iapetus": 747.4,
    "Phoebe": 112.,
    "Methone": 10.,
    "Anthe": 1.,
    "Pallene": 10.,
    "Telesto": 12.,
    "Helene": 16.,
}

__ORIGINS_DICT__ = {
    "Sun": " sun",
    "Venus": "venu",
    "Earth": "eart",
    "Jupiter": "jupi",
    "Io": "  io",
    "Europa": "euro",
    "Ganymede": "gany",
    "Callisto": "call",
    "Saturn baricentric": "sat1",
    "Saturn geocentric": "sat2",
    "Mimas": "mima",
    "Enceladus": "ence",
    "Tethys": "teth",
    "Dione": "dion",
    "Rhea": "rhea",
    "Titan": "tita",
    "Hyperion": "hyp",
    "Iapetus": "iape",
    "Phoebe": "phoe",
    "Methone": "meth",
    "Anthe": "anth",
    "Pallene": "pall",
    "Telesto": "tele",
    "Helene": "hele",
}

__COORDINATES_SYSTEMS_PER_ORIGINS_DICT__ = {
    "Sun": __SUN_COORDINATES__,
    "Venus": __PLANET_COORDINATES__,
    "Earth": __PLANET_COORDINATES__,
    "Jupiter": __PLANET_COORDINATES__,
    "Io": __SATELLITE_COORDINATES__,
    "Europa": __SATELLITE_COORDINATES__,
    "Ganymede": __SATELLITE_COORDINATES__,
    "Callisto": __SATELLITE_COORDINATES__,
    "Saturn baricentric": __SATURN_COORDINATES__,
    "Saturn geocentric": __SATURN_COORDINATES__,
    "Mimas": __SATELLITE_COORDINATES__,
    "Enceladus": __SATELLITE_COORDINATES__,
    "Tethys": __SATELLITE_COORDINATES__,
    "Dione": __SATELLITE_COORDINATES__,
    "Rhea": __SATELLITE_COORDINATES__,
    "Titan": __SATELLITE_COORDINATES__,
    "Hyperion": __SATELLITE_COORDINATES__,
    "Iapetus": __SATELLITE_COORDINATES__,
    "Phoebe": __SATELLITE_COORDINATES__,
    "Methone": __SATELLITE_COORDINATES__,
    "Anthe": __SATELLITE_COORDINATES__,
    "Pallene": __SATELLITE_COORDINATES__,
    "Telesto": __SATELLITE_COORDINATES__,
    "Helene": __SATELLITE_COORDINATES__,
}

__OBSERVERS_PER_ORIGINS_DICT__ = {
    "Sun": __SUN_OBSERVERS__,
    "Venus": __VENUS_OBSERVERS__,
    "Earth": __EARTH_OBSERVERS__,
    "Jupiter": __JUPITER_OBSERVERS__,
    "Io": __JUPITER_SATELLITE_OBSERVERS__,
    "Europa": __JUPITER_SATELLITE_OBSERVERS__,
    "Ganymede": __JUPITER_SATELLITE_OBSERVERS__,
    "Callisto": __JUPITER_SATELLITE_OBSERVERS__,
    "Saturn baricentric": __SATURN_OBSERVERS__,
    "Saturn geocentric": __SATURN_OBSERVERS__,
    "Mimas": __SATELLITE_SATELLITE_OBSERVERS__,
    "Enceladus": __SATELLITE_SATELLITE_OBSERVERS__,
    "Tethys": __SATELLITE_SATELLITE_OBSERVERS__,
    "Dione": __SATELLITE_SATELLITE_OBSERVERS__,
    "Rhea": __SATELLITE_SATELLITE_OBSERVERS__,
    "Titan": __SATELLITE_SATELLITE_OBSERVERS__,
    "Hyperion": __SATELLITE_SATELLITE_OBSERVERS__,
    "Iapetus": __SATELLITE_SATELLITE_OBSERVERS__,
    "Phoebe": __SATELLITE_SATELLITE_OBSERVERS__,
    "Methone": __SATELLITE_SATELLITE_OBSERVERS__,
    "Anthe": __SATELLITE_SATELLITE_OBSERVERS__,
    "Pallene": __SATELLITE_SATELLITE_OBSERVERS__,
    "Telesto": __SATELLITE_SATELLITE_OBSERVERS__,
    "Helene": __SATELLITE_SATELLITE_OBSERVERS__,
}

__TIME_RANGES__ = {
    "Voyager 1": DateTimeRange(datetime(1977, 9, 5, 14, 7), datetime(2030, 12, 31, 23, 58, 49)),
    "Voyager 2": DateTimeRange(datetime(1977, 8, 20, 15, 40, 9), datetime(2025, 12, 31, 23, 58, 49)),
    "Galileo": DateTimeRange(datetime(1989, 10, 19, 1, 28, 38), datetime(2003, 9, 30, 11, 58, 55)),
    "Ulysses": DateTimeRange(datetime(1990, 10, 6, 20, 26, 1), datetime(2050, 1, 1, 11, 58, 49)),
    "Cassini": DateTimeRange(datetime(1997, 10, 15, 9, 26, 10), datetime(2017, 9, 15, 10, 32, 49)),
    "Solar": DateTimeRange(datetime(1958, 1, 1), datetime(2094, 1, 1))
}

_FLOAT_REGEX = r'(-?\d+\.\d+)'
_YEARS_REGEX = r'(\d{4})'
_YEARDAY_REGEX = r'(\d{3})'
_HM_REGEX = r'(\d{2})'
_DATE_REGEX = f"{_YEARS_REGEX} {_YEARDAY_REGEX} {_HM_REGEX} {_HM_REGEX} {_FLOAT_REGEX}"


__CSV_HEADER_REGEX = re.compile(r"\s+([\w ]+)\s\(([\w\/]+)\)")

def _extract_headers(lines:List[str]) -> Tuple[int, List[List[str]]]:
    for index, line in enumerate(lines[:7]):
        match = __CSV_HEADER_REGEX.findall(line)
        if match:
            return index, match
    return -1,[]


def parse_trajectory(trajectory: str, product: ParameterIndex) -> Optional[SpeasyVariable]:
    def to_datetime(values):
        return datetime(int(values[0]), 1, 1, int(values[2]), int(values[3])) + timedelta(days=int(values[1]) - 1) + timedelta(
            milliseconds=int(values[4] * 1000.))

    lines = trajectory.splitlines()
    header_index, header = _extract_headers(lines)
    if header_index == -1:
        logging.error("Could not find header in trajectory data")
        return None
    columns, units = zip(*header)
    columns = columns[1:4]  # only keep X, Y, Z
    units = units[1:4]  # only keep X, Y, Z
    if units.count(units[0]) == len(units):
        units = units[0]
    values = np.empty((len(lines)-(header_index+2), len(columns)), dtype=np.float64)
    time = np.empty((len(lines)-(header_index+2),), dtype='datetime64[ns]')
    line_regex = re.compile(f"^{_DATE_REGEX}\\s+" + "\\s+".join([_FLOAT_REGEX]*len(columns)))
    index = 0
    for line in lines[header_index+2:]:
        match = line_regex.match(line)  # skip first 6 characters which are just spaces
        if match is not None:
            groups = match.groups()
            time[index] = np.datetime64(to_datetime(groups[0:4] + (float(groups[4]),)))
            for col in range(len(columns)):
                values[index, col] = float(groups[5 + col])
            index += 1
        else:
            logging.warning(f"Could not parse line: {line}")

    return SpeasyVariable(
        axes=[VariableTimeAxis(values=time)],
        values=DataContainer(values=values,
                                         meta={
                                             "UNITS": units,
                                             "COORDINATE_SYSTEM": product.CoordinateSystem,
                                             "ORIGIN": product.Origin,
                                             "ORIGIN_RADIUS": f"{product.OriginRadius} km",
                                             "OBSERVER": product.Observer,
                                             "DESCRIPTION": f"Trajectory of {product.Observer} in {product.CoordinateSystem} coordinates centered on {product.Origin}",
                                             "FILE_HEADER": "\n".join(lines[:header_index+2])
                                         },
                                         name=product.Observer),
        columns=columns,
    )


def _make_uid(origin: str, observer: str, coordinate_system: str):
    return f"{origin}_{observer}_{coordinate_system}"


def _make_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    return f"{prefix}/{product}/{start_time}"


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"uiowaephtool/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}', 'coordinate_system': kwargs.get('coordinate_system', 'gse')}


def build_trajectories(origin: str, coordinate_system: str) -> Dict[str, SpeasyIndex]:
    trajectories = {}
    for obs, code in __OBSERVERS_PER_ORIGINS_DICT__.get(origin, {}).items():
        meta = {
            'Id': code,
            'start_date': __TIME_RANGES__.get(obs, DateTimeRange(datetime(1958, 1, 1),
                                                                 datetime(2094, 1, 1))).start_time.isoformat(),
            'stop_date': __TIME_RANGES__.get(obs, DateTimeRange(datetime(1958, 1, 1),
                                                                datetime(2094, 1, 1))).stop_time.isoformat(),
            'CoordinateSystem': coordinate_system,
            'Origin': origin,
            'OriginRadius': __RADIUS_DICT__.get(origin, np.nan),
            'Observer': obs
        }
        trajectories[fix_name(obs)] = ParameterIndex(name=obs, provider='UiowaEphTool',
                                                     uid=_make_uid(origin, obs, coordinate_system), meta=meta)
    return trajectories


def build_coordinates_systems(origin: str) -> Dict[str, SpeasyIndex]:
    coordinates_systems = {}
    for coord, code in __COORDINATES_SYSTEMS_PER_ORIGINS_DICT__.get(origin, {}).items():
        meta = {'Id': code}
        meta.update(build_trajectories(origin, coord))
        coordinates_systems[fix_name(coord)] = SpeasyIndex(name=coord, provider='UiowaEphTool', uid=code, meta=meta)
    return coordinates_systems


def build_inventory() -> SpeasyIndex:
    trajs = {}
    for orig, code in __ORIGINS_DICT__.items():
        meta = {
            'Id': code,
            'Radius': __RADIUS_DICT__.get(orig, np.nan),
        }
        meta.update(build_coordinates_systems(orig))
        trajs[fix_name(orig)] = SpeasyIndex(name=orig, provider='UiowaEphTool', uid=code, meta=meta)

    return SpeasyIndex(name='Trajectories', provider='UiowaEphTool', uid='Trajectories', meta=trajs)


def make_index(meta: Dict):
    name = meta.pop('Name')
    meta['start_date'] = meta.pop('StartTime')
    meta['stop_date'] = meta.pop('EndTime')
    node = ParameterIndex(name=name, provider="UiowaEphTool", uid=meta['Id'], meta=meta)
    return node


class UiowaEphTool(DataProvider):
    BASE_URL = "https://planet.physics.uiowa.edu/das/casephem"

    def __init__(self):
        DataProvider.__init__(self, provider_name='uiowaephtool', provider_alt_names=['UiowaEphTool'],
                              min_proxy_version=Version("0.13.0"))

    def build_inventory(self, root: SpeasyIndex):
        root.Trajectories = build_inventory()
        return root

    def version(self, product):
        return 1

    def parameter_range(self, parameter_id: str or ParameterIndex) -> Optional[DateTimeRange]:
        """Get product time range.

        Parameters
        ----------
        parameter_id: str or ParameterIndex
            parameter id

        Returns
        -------
        Optional[DateTimeRange]
            Data time range

        Examples
        --------

        >>> import speasy as spz
        >>> spz.uiowaephtool.parameter_range("Callisto_Cassini_Co-rotational")
        <DateTimeRange: 1997-10-15T09:26:10+00:00 -> 2017-09-15T10:32:49+00:00>

        """
        return self._parameter_range(parameter_id)

    def get_data(self, product: str, start_time: datetime, stop_time: datetime, **kwargs) -> Optional[SpeasyVariable]:
        var = self._get_orbit(product=product, start_time=start_time, stop_time=stop_time, **kwargs)
        return var

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS)
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @Cacheable(prefix="UiowaEphTool_orbits", fragment_hours=lambda x: 24, version=version,
               entry_name=_make_cache_entry_name)
    @SplitLargeRequests(threshold=lambda x: timedelta(days=365))
    @Proxyfiable(GetProduct, get_parameter_args, min_version=Version("0.13.0"))
    def _get_orbit(self, product: str, start_time: datetime, stop_time: datetime,
                   extra_http_headers: Dict or None = None) -> Optional[SpeasyVariable]:
        if stop_time - start_time < timedelta(days=1):
            stop_time += timedelta(days=1)
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        if extra_http_headers is not None:
            headers.update(extra_http_headers)
        product = self._to_parameter_index(product)
        observer = __OBSERVERS_PER_ORIGINS_DICT__[product.Origin][product.Observer]
        origin = __ORIGINS_DICT__[product.Origin]
        coordinate_system = __COORDINATES_SYSTEMS_PER_ORIGINS_DICT__[product.Origin][product.CoordinateSystem]
        radius = __RADIUS_DICT__[product.Origin]
        res = http.post(self.BASE_URL,
                        headers=headers,
                        body=urlencode(
                            {
                                "StTime": start_time.strftime("%Y//%j %H:%M:%S"),
                                "SpTime": stop_time.strftime("%Y//%j %H:%M:%S"),
                                "TimeInterval": 60,
                                "origin": origin,
                                "observer": observer,
                                "coordinates": coordinate_system,
                                "OriginName": product.Origin,
                                "OriginRadius": str(radius)
                            }
                        )
                        )
        if res.ok:
            maybe_var = parse_trajectory(res.text, product=product)
            if maybe_var is not None:
                return maybe_var[start_time:stop_time]
        else:
            log.debug(f"Could not get trajectory for {product.spz_uid()} between {start_time} and {stop_time}")
            log.debug(f"Status code: {res.status_code}")
            log.debug(res.text)
        return None
