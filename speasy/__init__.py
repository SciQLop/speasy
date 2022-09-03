# -*- coding: utf-8 -*-
"""
.. testsetup:: *

   import speasy as spz

"""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.10.2'
__all__ = ['amda', 'cda', 'ssc', 'get_data', 'get_orbit', 'SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable']
__docformat__ = "numpy"

from speasy.core.inventory.indexes import SpeasyIndex
from .products import SpeasyVariable, Catalog, Event, Dataset, TimeTable, MaybeAnyProduct
from . import webservices as _ws
from typing import List

amda = _ws.AMDA_Webservice()
cda = _ws.CDA_Webservice()
ssc = _ws.SSC_Webservice()
csa = _ws.CSA_Webservice()

__PROVIDERS__ = {
    'amda': amda.get_data,
    'cdaweb': cda.get_data,
    'cda': cda.get_data,
    'sscweb': ssc.get_trajectory,
    'ssc': ssc.get_trajectory,
    'csa': csa.get_data
}


# @TODO implement me, this function should be able to look inside all servers
# and return something that could be passed to get_data
def find_product(name: str) -> List[str]:
    pass


def provider_and_product(path_or_product: str or SpeasyIndex) -> (str, str):
    """Breaks given product in two parts: provider and product UID

    Parameters
    ----------
    path_or_product : str or SpeasyIndex
        The product as SpeasyIndex or path as string you want to split
    Returns
    -------
    (str, str)
        the provider UID and the product UID
    """
    if isinstance(path_or_product, SpeasyIndex):
        return path_or_product.spz_provider().lower(), path_or_product.spz_uid()
    elif type(path_or_product) is str:
        if '/' in path_or_product:
            provider_uid, product_uid = path_or_product.split('/', 1)
            return provider_uid, product_uid
        else:
            raise ValueError(f"Given string does not look like a path {path_or_product}")
    raise TypeError(
        f"Wrong type for {path_or_product}, expecting a string or a SpeasyIndex, got {type(path_or_product)}")


def get_data(product: str or SpeasyIndex, start_time=None, stop_time=None, **kwargs) -> MaybeAnyProduct:
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
    MaybeAnyProduct
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
    provider_uid, product_uid = provider_and_product(product)
    if provider_uid in __PROVIDERS__:
        return __PROVIDERS__[provider_uid](product_uid, start_time=start_time, stop_time=stop_time, **kwargs)

    raise ValueError(
        f"Can't find a provider for {product}")


def get_orbit(body: str or SpeasyIndex, start_time, stop_time, coordinate_system: str = 'gse',
              **kwargs) -> SpeasyVariable:
    return ssc.get_trajectory(body, start_time, stop_time, coordinate_system=coordinate_system, **kwargs)


def list_providers() -> List[str]:
    return list(__PROVIDERS__.keys())


def update_inventories(disable_cache=False, force_refresh=False):
    from .core.dataprovider import PROVIDERS
    for provider in PROVIDERS.values():
        provider.update_inventory(disable_cache=disable_cache, force_refresh=force_refresh)
