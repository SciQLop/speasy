# -*- coding: utf-8 -*-

"""cdaweb package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import os
from typing import Optional
from datetime import datetime
import requests
from ..cache import _cache, Cacheable
from ..common.variable import SpwcVariable
from ..proxy import Proxyfiable, GetProduct
import numpy as np
from astropy import units


def _variable(orbit: dict) -> Optional[SpwcVariable]:
    data = orbit['Result']['Data'][1][0]['Coordinates'][1][0]
    keys = list(data.keys())
    keys.remove('CoordinateSystem')
    values = np.array([data[key][1] for key in keys]).transpose() * units.km
    # this is damn slow!
    time = np.array([datetime.strptime(v[1], '%Y-%m-%dT%H:%M:%S.%f%z').timestamp() for v in
                     orbit['Result']['Data'][1][0]['Time'][1]])
    return SpwcVariable(time=time,
                        data=values,
                        meta={'CoordinateSystem': data['CoordinateSystem']},
                        columns=keys)


def _is_valid(orbit: dict):
    return orbit['Result']['StatusCode'] == 'SUCCESS' and orbit['Result']['StatusSubCode'] == 'SUCCESS'


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"sscweb/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}


class SscWeb:
    def __init__(self):
        self.__url = "https://sscweb.gsfc.nasa.gov/WS/sscr/2"

    def get_observatories(self):
        res = requests.get(f"{self.__url}/observatories", headers={"Accept": "application/json"})
        if not res.ok:
            return None
        return res.json()['Observatory'][1]

    def version(self, product):
        return 1

    @Cacheable(prefix="ssc_orbits", fragment_hours=lambda x: 24, version=version)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_orbit(self, product: str, start_time: datetime, stop_time: datetime, coordinate_system: str = 'gse',
                  debug=False) -> Optional[SpwcVariable]:
        url = f"{self.__url}/locations/{product}/{start_time.strftime('%Y%m%dT%H%M%SZ')},{stop_time.strftime('%Y%m%dT%H%M%SZ')}/{coordinate_system}/"
        if debug:
            print(url)
        res = requests.get(url, headers={"Accept": "application/json"})
        orbit = res.json()
        if res.ok and _is_valid(orbit):
            return _variable(orbit)
        return None
