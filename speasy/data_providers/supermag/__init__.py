# -*- coding: utf-8 -*-

"""SuperMAG data provider.

Gives access to `SuperMAG <https://supermag.jhuapl.edu>`__ (JHUAPL) ground
magnetometer stations through the SuperMAG web services (direct HTTP).

"""

__author__ = "Richard Hitier"
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np

from speasy.config import supermag as supermag_cfg
from speasy.core import http, EnsureUTCDateTime, AllowedKwargs
from speasy.core.algorithms import fix_name
from speasy.core.cache import CacheCall, Cacheable, CACHE_ALLOWED_KWARGS
from speasy.core.dataprovider import DataProvider, GET_DATA_ALLOWED_KWARGS, ParameterRangeCheck
from speasy.core.datetime_range import DateTimeRange
from speasy.core.impex.exceptions import MissingCredentials
from speasy.core.inventory.indexes import (ParameterIndex, SpeasyIndex,
                                           make_inventory_node)
from speasy.core.proxy import PROXY_ALLOWED_KWARGS
from speasy.core.requests_scheduling import SplitLargeRequests
from speasy.products.variable import SpeasyVariable, VariableTimeAxis, DataContainer

log = logging.getLogger(__name__)

# Public station-list endpoint. Returns a JSON array of all stations with their
# IAGA code, geographic coordinates, name and operator(s). No logon required.
_STATIONS_URL = "https://supermag.jhuapl.edu/lib/services/?service=stations&fmt=json"

# SuperMAG stores its no-data sentinel as this value in every numeric field.
_MISSING_VALUE = 999999

# Stations carry no per-station coverage dates, instead, supermag api provides per time range stations list.
#  So a single generous range guards is set against absurd time requests (see
#  uiowa_eph_tool for the same approach).
_COVERAGE = DateTimeRange(datetime(1970, 1, 1), datetime(2100, 1, 1))

#
# All the SuperMag indices extracted from the website at
#  https://supermag.jhuapl.edu/indices
#
# and from the api url
#  https://supermag.jhuapl.edu/services/indices.php?nohead&logon=<myid>&start=2020-01-01T00:00&extent=120&indices=all&swi=all&imf=all
# 
# Stored here as a static list of dicts so we dont depend from an url fetch  with logon
#
_INDEX_FAMILIES = [
    {'name': 'AuroralElectrojet', 'label': 'Auroral Electrojet Indices', 'indices': [
        {'key': 'SME_U_L', 'label': 'SME U/L', 'units': 'nT', 'index_keys': ['SMU', 'SML'],
         'description': 'Upper and lower electrojet envelopes (SMU, SML)'},
        {'key': 'SME', 'label': 'SME', 'units': 'nT', 'index_keys': ['SME'],
         'description': 'Auroral electrojet envelope amplitude (SMU - SML)'},
        {'key': 'SME_MLT', 'label': 'SME MLT', 'units': 'h', 'index_keys': ['SMLmlt', 'SMUmlt'],
         'description': 'Magnetic local time of the SML/SMU extrema'},
        {'key': 'SME_MLAT', 'label': 'SME MLAT', 'units': 'deg', 'index_keys': ['SMLmlat', 'SMUmlat'],
         'description': 'Magnetic latitude of the SML/SMU extrema'},
        {'key': 'SME_nstations', 'label': 'SME #stations', 'units': 'count', 'index_keys': ['SMEnum'],
         'description': 'Number of stations used to compute SME'},
    ]},
    {'name': 'RingCurrent', 'label': 'Ring Current Indices', 'indices': [
        {'key': 'SMR', 'label': 'SMR', 'units': 'nT', 'index_keys': ['smr'],
         'description': 'Ring current index, global (SYM-H/Dst-like)'},
        {'key': 'SMR_LT', 'label': 'SMR LT', 'units': 'nT',
         'index_keys': ['smr00', 'smr06', 'smr12', 'smr18'],
         'description': 'Ring current index by MLT sector (00/06/12/18)'},
        {'key': 'SMR_nstations', 'label': 'SMR #stations', 'units': 'count', 'index_keys': ['smrnum'],
         'description': 'Number of stations used to compute SMR'},
    ]},
    {'name': 'SolarWind', 'label': 'Solar Wind Parameters', 'indices': [
        {'key': 'B_GSM', 'label': 'B field (GSM)', 'units': 'nT', 'index_keys': ['bgsm'],
         'components': ['X', 'Y', 'Z'], 'description': 'Solar wind magnetic field vector, GSM'},
        {'key': 'B_GSE', 'label': 'B field (GSE)', 'units': 'nT', 'index_keys': ['bgse'],
         'components': ['X', 'Y', 'Z'], 'description': 'Solar wind magnetic field vector, GSE'},
        {'key': 'V_GSM', 'label': 'V (GSM)', 'units': 'km/s', 'index_keys': ['vgsm'],
         'components': ['X', 'Y', 'Z'], 'description': 'Solar wind velocity vector, GSM'},
        {'key': 'V_GSE', 'label': 'V (GSE)', 'units': 'km/s', 'index_keys': ['vgse'],
         'components': ['X', 'Y', 'Z'], 'description': 'Solar wind velocity vector, GSE'},
        {'key': 'dynamic_pressure', 'label': 'Dynamic Pressure', 'units': 'nPa', 'index_keys': ['dynpres'],
         'description': 'Solar wind dynamic pressure'},
        {'key': 'plasma_density', 'label': 'Plasma Density', 'units': 'cm^-3', 'index_keys': ['density'],
         'description': 'Solar wind plasma density'},
        {'key': 'newell', 'label': 'Newell', 'units': 'Wb/s', 'index_keys': ['newell'],
         'description': 'Newell solar wind-magnetosphere coupling function'},
        {'key': 'epsilon', 'label': 'ε Parameter', 'units': 'GW', 'index_keys': ['epsilon'],
         'description': 'Akasofu epsilon coupling parameter'},
        {'key': 'clock_GSM', 'label': 'IMF Clock Angle (GSM)', 'units': 'deg', 'index_keys': ['clockgsm'],
         'description': 'IMF clock angle, GSM'},
        {'key': 'clock_GSE', 'label': 'IMF Clock Angle (GSE)', 'units': 'deg', 'index_keys': ['clockgse'],
         'description': 'IMF clock angle, GSE'},
    ]},
]


def _cache_entry_name(prefix: str, product: str, start_time: str, **kwargs) -> str:
    # The logon is deliberately excluded from the cache key (it is a user secret,
    # not a property of the data); ``coordinates`` is included since it changes values.
    return f"{prefix}/{product}/{kwargs.get('coordinates', 'nez')}/{start_time}"


def _records_to_variable(records: List[Dict], coordinates: str, station: str) -> Optional[SpeasyVariable]:
    """Map a SuperMAG ``data-api`` list-of-dicts response to a SpeasyVariable.

    Each record carries a Unix-seconds ``tval`` and the N/E/Z components as
    ``{'nez': ..., 'geo': ...}`` sub-dicts; ``coordinates`` selects the frame.
    """
    if not records:
        return None
    tvals = np.array([r['tval'] for r in records], dtype='float64')
    time_axis = (tvals * 1e9).astype('int64').astype('datetime64[ns]')
    values = np.array([[r['N'][coordinates], r['E'][coordinates], r['Z'][coordinates]]
                       for r in records], dtype='float64')
    values[values == _MISSING_VALUE] = np.nan
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=time_axis)],
        values=DataContainer(values, name='B',
                             meta={'UNITS': 'nT', 'COORDINATE_SYSTEM': coordinates, 'station': station}),
        columns=['N', 'E', 'Z'])


class SuperMAGWebservice(DataProvider):
    BASE_URL = "https://supermag.jhuapl.edu"

    def __init__(self):
        # Dont proxify the inventory ... to be confirmed
        DataProvider.__init__(self, provider_name='supermag', provider_alt_names=['SuperMAG'],
                              inventory_disable_proxy=True)

    def version(self, product):  # NOSONAR (S1172) - kept for the @Cacheable version protocol
        return 1

    @CacheCall(cache_retention=7 * 24 * 60 * 60, is_pure=True)
    def _get_stations(self) -> List[Dict]:
        """Return the SuperMAG station list from the public endpoint (no logon)."""
        res = http.get(_STATIONS_URL, headers={"Accept": "application/json"})
        if not res.ok:
            log.warning(f"Failed to fetch SuperMAG station list ({res.status_code})")
            return []
        return res.json()

    def build_inventory(self, root: SpeasyIndex) -> SpeasyIndex:
        # Indices first: they need no logon and no network, so the Indices tree is present
        # even if the stations endpoint glitches (200 + non-JSON body raises in _get_stations).
        self._build_indices_inventory(root)
        stations_node = make_inventory_node(root, SpeasyIndex, name='Stations',
                                            provider='supermag', uid='Stations')
        for station in self._get_stations():
            iaga_id = station['id']
            make_inventory_node(stations_node, ParameterIndex, name=fix_name(iaga_id),
                                provider='supermag', uid=f'Stations/{iaga_id}',
                                station=iaga_id, label=station.get('name', iaga_id),
                                geolat=station.get('geolat'), geolon=station.get('geolon'),
                                operator=station.get('operator'),
                                start_date=_COVERAGE.start_time.isoformat(),
                                stop_date=_COVERAGE.stop_time.isoformat())
        return root

    @staticmethod
    def _build_indices_inventory(root: SpeasyIndex) -> None:
        """Build the static, logon-free Indices tree (grouped by SuperMAG's own families)."""
        indices_root = make_inventory_node(root, SpeasyIndex, name='Indices',
                                            provider='supermag', uid='Indices')
        for family in _INDEX_FAMILIES:
            family_node = make_inventory_node(indices_root, SpeasyIndex, name=family['name'],
                                              provider='supermag', uid=f"Indices/{family['name']}",
                                              label=family['label'])
            for index in family['indices']:
                meta = {k: index[k] for k in ('label', 'units', 'description', 'index_keys')}
                if 'components' in index:
                    meta['components'] = index['components']
                make_inventory_node(family_node, ParameterIndex, name=index['key'],
                                    provider='supermag', uid=f"Indices/{index['key']}", **meta)

    def get_data(self, product: str, start_time, stop_time, coordinates: str = 'nez',
                 **kwargs) -> Optional[SpeasyVariable]:
        if not product.startswith('Stations/'):
            raise NotImplementedError(
                "SuperMAG indices download is not implemented yet; only station products "
                "(supermag/Stations/<IAGA>) can be downloaded.")
        return self._get_station_data(product=product, start_time=start_time, stop_time=stop_time,
                                      coordinates=coordinates, **kwargs)

    def parameter_range(self, parameter_id) -> Optional[DateTimeRange]:
        """Return the coverage range of a SuperMAG station.

        All stations share a single generous range (SuperMAG exposes no
        per-station coverage dates, but per time-period stations list);
        This only guards against absurd time requests.
        """
        return self._parameter_range(parameter_id)

    @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS + ['coordinates'])
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @Cacheable(prefix="supermag", fragment_hours=lambda x: 24, version=version, entry_name=_cache_entry_name)
    @SplitLargeRequests(threshold=lambda x: timedelta(days=30))
    def _get_station_data(self, product: str, start_time, stop_time, coordinates: str = 'nez',
                          extra_http_headers: Optional[Dict] = None, **kwargs) -> Optional[SpeasyVariable]:
        logon = supermag_cfg.logon()
        if not logon:
            raise MissingCredentials(
                "SuperMAG requires a logon. Set it with spz.config.supermag.logon.set('<userid>') "
                "or the SPEASY_SUPERMAG_LOGON environment variable.")
        iaga = product.rsplit('/', 1)[-1]
        url = (f"{self.BASE_URL}/services/data-api.php?fmt=json&nohead"
               f"&logon={logon}&start={start_time.strftime('%Y-%m-%dT%H:%M')}"
               f"&extent={int((stop_time - start_time).total_seconds())}&station={iaga}")
        log.debug(f"Requesting SuperMAG data for station {iaga}")
        headers = {"Accept": "application/json"}
        if extra_http_headers is not None:
            headers.update(extra_http_headers)
        res = http.get(url, headers=headers)
        if not res.ok:
            log.warning(f"SuperMAG data request failed ({res.status_code}) for station {iaga}")
            return None
        try:
            records = res.json()
        except ValueError:
            # SuperMAG answers HTTP 200 with a non-JSON body on logon/server-side errors.
            # has to be noted that the server errors are not always regular
            log.warning(f"SuperMAG returned a non-JSON response for station {iaga} "
                        f"(logon or server-side error)")
            return None
        var = _records_to_variable(records, coordinates, iaga)
        if var is not None:
            return var[start_time:stop_time]
        return None
