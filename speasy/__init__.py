# -*- coding: utf-8 -*-
"""
.. testsetup:: *

   import speasy as spz

"""

import logging
from importlib import metadata as _metadata

log = logging.getLogger(__name__)

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
try:
    __version__ = _metadata.version("speasy")
except _metadata.PackageNotFoundError:  # running from a source tree, never installed
    __version__ = "0.0.0.dev0"
__docformat__ = "numpy"

from typing import List

from speasy.core.inventory.indexes import SpeasyIndex
from .products import SpeasyVariable, Catalog, Event, Dataset, TimeTable, MaybeAnyProduct

# keep this import last
from .core.requests_scheduling.request_dispatch import get_data, list_providers
from .core.dataprovider import registered_providers as _registered_providers

__all__ = ['get_data', 'SpeasyVariable', 'Catalog', 'Event', 'Dataset', 'TimeTable', *_registered_providers()]


def __getattr__(name):
    from .core.requests_scheduling import request_dispatch
    if name in _registered_providers():
        return getattr(request_dispatch, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted({*globals(), *_registered_providers()})


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
        try:
            provider.update_inventory()
        except Exception:
            # One provider's outage must not prevent the others from refreshing.
            log.warning(f"Failed to refresh inventory for provider {provider.provider_name}", exc_info=True)
