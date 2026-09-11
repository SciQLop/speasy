"""Virtual products: products computed locally instead of fetched from a web service."""

from typing import Callable, Dict

from ..core.inventory import ProviderInventory
from ..core.inventory.indexes import SpeasyIndex
from ..core.requests_scheduling.request_dispatch import PROVIDERS
from ..inventories import tree, flat_inventories

_callbacks: Dict[str, Callable] = {}
_root = SpeasyIndex(name="virtual", provider="virtual", uid="virtual")
_flat_inventory = ProviderInventory()


def _register(product_uid: str, callback: Callable):
    """Serve callback(start_time, stop_time) as the product 'virtual/<product_uid>'.

    Internal on purpose: the public registration API, which takes a full path and
    returns a callable handle, comes with the decorator.
    """
    _callbacks[product_uid] = callback


class _VirtualProvider:
    """Serves virtual products through speasy's dispatch table.

    Deliberately not a DataProvider subclass: get_data() is the whole contract the
    dispatcher needs, while DataProvider.__init__ would fetch an inventory through
    the proxy for products that are local by definition.
    """

    def get_data(self, product_uid: str, start_time, stop_time, **kwargs):
        callback = _callbacks.get(product_uid)
        if callback is None:
            raise ValueError(f"Unknown virtual product 'virtual/{product_uid}'")
        return callback(start_time, stop_time)


def _init_virtual_provider():
    """Register the virtual provider in the dispatch table and its inventory."""
    PROVIDERS['virtual'] = _VirtualProvider()
    tree.__dict__['virtual'] = _root
    flat_inventories.__dict__['virtual'] = _flat_inventory

_init_virtual_provider()
