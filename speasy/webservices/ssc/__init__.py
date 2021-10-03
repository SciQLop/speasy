# -*- coding: utf-8 -*-

"""cda package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

from typing import Optional
from datetime import datetime, timedelta
from speasy.core.cache import Cacheable, CacheCall
from speasy.products.variable import SpeasyVariable
from ...core import http
from speasy.core.proxy import Proxyfiable, GetProduct
from .indexes import SscwebParameterIndex
from speasy.inventory import data_tree
import numpy as np
from astropy import units

import logging

log = logging.getLogger(__name__)


def _variable(orbit: dict) -> Optional[SpeasyVariable]:
    data = orbit['Result']['Data'][1][0]['Coordinates'][1][0]
    keys = list(data.keys())
    keys.remove('CoordinateSystem')
    values = np.array([data['X'][1], data['Y'][1], data['Z'][1]]).transpose() * units.km
    # this is damn slow!
    time = np.array([datetime.strptime(v[1], '%Y-%m-%dT%H:%M:%S.%f%z').timestamp() for v in
                     orbit['Result']['Data'][1][0]['Time'][1]])
    return SpeasyVariable(time=time,
                          data=values,
                          meta={'CoordinateSystem': data['CoordinateSystem']},
                          columns=['X', 'Y', 'Z'])


def _is_valid(orbit: dict):
    return orbit['Result']['StatusCode'] == 'SUCCESS' and orbit['Result']['StatusSubCode'] == 'SUCCESS'


def _make_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    return f"{prefix}/{product}/{kwargs.get('coordinate_system', 'gse')}/{start_time}"


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"sscweb/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}', 'coordinate_system': kwargs.get('coordinate_system', 'gse')}


class SSC_Webservice:
    def __init__(self):
        self.__url = "https://sscweb.gsfc.nasa.gov/WS/sscr/2"
        self.update_inventory()

    def update_inventory(self):
        inv = list(map(SscwebParameterIndex, self.get_observatories()))
        data_tree.ssc.Trajectories.__dict__.update({item.Id: item for item in inv})

    @CacheCall(cache_retention=7 * 24 * 60 * 60, is_pure=True)
    def get_observatories(self):
        res = http.get(f"{self.__url}/observatories", headers={"Accept": "application/json"})
        if not res.ok:
            return None
        return res.json()['Observatory'][1]

    def version(self, product):
        return 2

    # Wrapper to ensure that whatever the source (Proxy, Cache, SSCWeb) the returned variable is in km
    def get_orbit(self, product: str, start_time: datetime, stop_time: datetime, coordinate_system: str = 'gse',
                  debug=False, **kwargs) -> Optional[SpeasyVariable]:
        var = self._get_orbit(product=product, start_time=start_time, stop_time=stop_time,
                              coordinate_system=coordinate_system, debug=debug, **kwargs)
        if var:
            if not hasattr(var.values, 'unit'):
                var.values *= units.km
        return var

    @Cacheable(prefix="ssc_orbits", fragment_hours=lambda x: 24, version=version, entry_name=_make_cache_entry_name)
    @Proxyfiable(GetProduct, get_parameter_args)
    def _get_orbit(self, product: str, start_time: datetime, stop_time: datetime, coordinate_system: str = 'gse',
                   debug=False) -> Optional[SpeasyVariable]:
        if stop_time - start_time < timedelta(days=1):
            stop_time += timedelta(days=1)
        url = f"{self.__url}/locations/{product}/{start_time.strftime('%Y%m%dT%H%M%SZ')},{stop_time.strftime('%Y%m%dT%H%M%SZ')}/{coordinate_system.lower()}/"
        if debug:
            print(url)
        res = http.get(url, headers={"Accept": "application/json"})
        orbit = res.json()
        if res.ok and _is_valid(orbit):
            return _variable(orbit)[start_time:stop_time]
        return None
