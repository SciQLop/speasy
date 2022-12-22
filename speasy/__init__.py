# -*- coding: utf-8 -*-
"""
.. testsetup:: *

   import speasy as spz

"""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '1.0.5'
__all__ = ['amda', 'cda', 'ssc', 'csa', 'get_data', 'SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable']
__docformat__ = "numpy"

from speasy.core.inventory.indexes import SpeasyIndex
from .products import SpeasyVariable, Catalog, Event, Dataset, TimeTable, MaybeAnyProduct
from typing import List
from .core.requests_scheduling.request_dispatch import get_data, list_providers, amda, cda, csa, ssc


# @TODO implement me, this function should be able to look inside all servers
# and return something that could be passed to get_data
def find_product(name: str) -> List[str]:
    pass


def update_inventories():
    from .core.dataprovider import PROVIDERS
    for provider in PROVIDERS.values():
        provider.update_inventory()
