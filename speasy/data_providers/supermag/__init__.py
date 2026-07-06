# -*- coding: utf-8 -*-

"""SuperMAG data provider.

Gives access to `SuperMAG <https://supermag.jhuapl.edu>`__ (JHUAPL) ground
magnetometer stations through the SuperMAG web services (direct HTTP).

"""

__author__ = "Richard Hitier"
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import logging
from typing import Dict, List

from speasy.core import http
from speasy.core.algorithms import fix_name
from speasy.core.cache import CacheCall
from speasy.core.dataprovider import DataProvider
from speasy.core.inventory.indexes import (ParameterIndex, SpeasyIndex,
                                           make_inventory_node)

log = logging.getLogger(__name__)

# Public station-list endpoint. Returns a JSON array of all stations with their
# IAGA code, geographic coordinates, name and operator(s). No logon required.
_STATIONS_URL = "https://supermag.jhuapl.edu/lib/services/?service=stations&fmt=json"


class SuperMAGWebservice(DataProvider):
    BASE_URL = "https://supermag.jhuapl.edu"

    def __init__(self):
        DataProvider.__init__(self, provider_name='supermag', provider_alt_names=['SuperMAG'])

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
        stations_node = make_inventory_node(root, SpeasyIndex, name='Stations',
                                            provider='supermag', uid='Stations')
        for station in self._get_stations():
            iaga_id = station['id']
            make_inventory_node(stations_node, ParameterIndex, name=fix_name(iaga_id),
                                provider='supermag', uid=f'Stations/{iaga_id}',
                                station=iaga_id, label=station.get('name', iaga_id),
                                geolat=station.get('geolat'), geolon=station.get('geolon'),
                                operator=station.get('operator'))
        return root
