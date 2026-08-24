# -*- coding: utf-8 -*-
"""
.. testsetup:: *

   import speasy as spz

"""

from importlib import metadata as _metadata

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
try:
    __version__ = _metadata.version("speasy")
except _metadata.PackageNotFoundError:  # running from a source tree, never installed
    __version__ = "0.0.0.dev0"
__all__ = ['amda', 'cda', 'ssc', 'csa', 'cdpp3dview', 'get_data', 'archive', 'SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable']
__docformat__ = "numpy"

from typing import List

from speasy.core.inventory.indexes import SpeasyIndex
from .products import SpeasyVariable, Catalog, Event, Dataset, TimeTable, MaybeAnyProduct

# keep this import last
from .core.requests_scheduling.request_dispatch import get_data, list_providers, amda, cda, csa, ssc, archive, uiowaephtool, cdpp3dview


# @TODO implement me, this function should be able to look inside all servers
# and return something that could be passed to get_data
def find_product(name: str) -> List[str]:
    raise NotImplementedError("Not implemented yet")


def update_inventories():
    from .core.dataprovider import PROVIDERS
    from .core.requests_scheduling.request_dispatch import init_providers
    # Retries any provider whose one-shot init at import time failed (e.g. a
    # transient error reaching its web service); a no-op for providers already
    # initialized, see _safe_init_provider.
    init_providers()
    for provider in PROVIDERS.values():
        provider.update_inventory()
