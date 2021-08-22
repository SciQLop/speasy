# -*- coding: utf-8 -*-
"""
.. testsetup:: *

   import speasy as spz

"""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.9.0'
__all__ = ['amda', 'cda', 'ssc', 'get_data', 'get_orbit', 'SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable']
__docformat__ = "numpy"

from .inventory.indexes import SpeasyIndex
from .products import SpeasyVariable, Catalog, Event, Dataset, TimeTable
from . import webservices
from typing import List, Union, Optional

amda = webservices.AMDA_Webservice()
cda = webservices.CDA_Webservice()
ssc = webservices.SSC_Webservice()

__PROVIDERS__ = {
    'amda': amda.get_data,
    'cdaweb': cda.get_data,
    'sscweb': ssc.get_orbit
}


# @TODO implement me, this function should be able to look inside all servers
# and return something that could be passed to get_data
def find_product(name: str) -> List[str]:
    pass


def get_data(product: str or SpeasyIndex, start_time=None, stop_time=None, **kwargs) -> Optional[
    Union[Dataset, SpeasyVariable, TimeTable, Catalog]]:
    """Download given product, this function accepts string paths like "sscweb/moon" or index objects
    from inventory trees.

    Parameters
    ----------
    product : str or SpeasyIndex
        The product you want to download, either path like "sscweb/moon" or index objects.
    start_time : str or datetime.datetime, optional
        Start time, mandatory for time-series.
    stop_time : str or datetime.datetime, optional
        Stop time, mandatory for time-series.
    kwargs

    Returns
    -------
    Optional[Union[Dataset, SpeasyVariable, TimeTable, Catalog]]
        The requested product if available or None

    Examples
    --------
    >>> moon=spz.get_data('sscweb/moon', '2000-01-01', '2000-09-02T12:00:00+00:00')
    >>> moon.columns
    ['X', 'Y', 'Z']
    >>> moon.data
    <Quantity [[ 183940.73767809, -354329.74995782,   36559.09278865],
               [ 183989.39891203, -354307.09633046,   36558.99256677],
               [ 184038.04489285, -354284.42184423,   36558.88913279],
               ...,
               [ 230448.57392717,  305986.424528  ,   33999.47652102],
               [ 230405.72253792,  306023.74218105,   33998.89651167],
               [ 230362.93800137,  306061.10305253,   33998.32408929]] km>


    """
    if isinstance(product, SpeasyIndex):
        provider = product.provider.lower()
        if provider in __PROVIDERS__:
            return __PROVIDERS__[provider](product, start_time, stop_time, **kwargs)
    else:
        components = product.split('/')
        provider = components[0]
        if provider in __PROVIDERS__:
            return __PROVIDERS__[provider]('/'.join(components[1:]), start_time=start_time, stop_time=stop_time,
                                           **kwargs)
    raise ValueError(
        f'{components[0]} not found in data provider list\nSupported providers are:\n{list(__PROVIDERS__.keys())}')


def get_orbit(body: str, start_time, stop_time, coordinate_system: str = 'gse', **kwargs) -> SpeasyVariable:
    return ssc.get_orbit(body, start_time, stop_time, coordinate_system=coordinate_system, **kwargs)


def list_providers() -> List[str]:
    return list(__PROVIDERS__.keys())
