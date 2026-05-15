"""
.. testsetup:: *

   import speasy as spz

"""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("speasy")
except _PackageNotFoundError:
    # Source checkout without an editable install — degrade gracefully so
    # imports don't crash. Normal dev workflow (`uv sync`) creates the
    # .dist-info so this fallback isn't hit.
    __version__ = "0.0.0+dev"
__all__ = [
    'Catalog',
    'Dataset',
    'Event',
    'MaybeAnyProduct',
    'SpeasyIndex',
    'SpeasyVariable',
    'TimeTable',
    'amda',
    'archive',
    'cda',
    'cdpp3dview',
    'csa',
    'get_data',
    'list_providers',
    'ssc',
    'uiowaephtool',
]
__docformat__ = "numpy"

from speasy.core.inventory.indexes import SpeasyIndex  # noqa: I001  # reason: ordering matters to avoid circular imports

from .products import Catalog, Dataset, Event, MaybeAnyProduct, SpeasyVariable, TimeTable

# keep this import last
from .core.requests_scheduling.request_dispatch import (
    amda,
    archive,
    cda,
    cdpp3dview,
    csa,
    get_data,
    list_providers,
    ssc,
    uiowaephtool,
)


# @TODO implement me, this function should be able to look inside all servers
# and return something that could be passed to get_data
def find_product(name: str) -> list[str]:
    raise NotImplementedError("Not implemented yet")


def update_inventories():
    from .core.dataprovider import PROVIDERS
    for provider in PROVIDERS.values():
        provider.update_inventory()
