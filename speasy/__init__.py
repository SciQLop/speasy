# -*- coding: utf-8 -*-
"""
.. testsetup:: *

   import speasy as spz

"""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '1.5.2'
__all__ = ['amda', 'cda', 'ssc', 'csa', 'get_data', 'archive', 'SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable']
__docformat__ = "numpy"

from typing import List

from speasy.core.inventory.indexes import SpeasyIndex
from .products import SpeasyVariable, Catalog, Event, Dataset, TimeTable, MaybeAnyProduct

# keep this import last
from .core.requests_scheduling.request_dispatch import get_data, list_providers, amda, cda, csa, ssc, archive


# @TODO implement me, this function should be able to look inside all servers
# and return something that could be passed to get_data
def find_product(name: str) -> List[str]:
    raise NotImplementedError("Not implemented yet")


def update_inventories():
    from .core.dataprovider import PROVIDERS
    for provider in PROVIDERS.values():
        provider.update_inventory()
