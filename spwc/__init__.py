# -*- coding: utf-8 -*-

"""Top-level package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.8.0'

from .common.variable import SpwcVariable
from .amda import AMDA
from .cdaweb import cdaweb as cd
from .sscweb import SscWeb
from typing import List

amda = AMDA()
cda = cd()
ssc = SscWeb()

__PROVIDERS__ = {
    'amda': amda.get_data,
    'cdaweb': cda.get_data,
    'sscweb': ssc.get_orbit
}


# @TODO implement me, this function should be able to look inside all servers
# and return something that could be passed to get_data
def find_product(name: str) -> List[str]:
    pass


def get_data(path: str, start_time, stop_time, **kwargs) -> SpwcVariable:
    components = path.split('/')
    if components[0] in __PROVIDERS__:
        return __PROVIDERS__[components[0]]('/'.join(components[1:]), start_time=start_time, stop_time=stop_time,
                                            **kwargs)
    raise ValueError(f'{components[0]} not found in data provider list')


def get_orbit(body: str, start_time, stop_time, coordinate_system: str = 'gse', **kwargs) -> SpwcVariable:
    return ssc.get_orbit(body, start_time, stop_time, coordinate_system=coordinate_system, **kwargs)
