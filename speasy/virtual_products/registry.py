"""Virtual products: products computed locally instead of fetched from a web service."""

from typing import Callable, Dict, Optional

from ..core.inventory import ProviderInventory
from ..core.inventory.indexes import ParameterIndex, SpeasyIndex, make_inventory_node
from ..core.requests_scheduling.request_dispatch import PROVIDERS
from ..inventories import tree, flat_inventories

_callbacks: Dict[str, Callable] = {}
_root = SpeasyIndex(name="virtual", provider="virtual", uid="virtual")
_flat_inventory = ProviderInventory()


def _path_to_uid(path: str) -> str:
    """Turn the public path 'virtual/plasma/beta' into the registry uid 'plasma/beta'."""
    if not isinstance(path, str):
        raise TypeError(f"virtual product path must be a str, got {type(path).__name__}")
    provider, _, uid = path.partition('/')
    if provider != 'virtual' or not uid or not all(seg.strip() for seg in uid.split('/')):
        raise ValueError(f"virtual product path must look like 'virtual/<path>', got {path!r}")
    return uid


class VirtualProduct(ParameterIndex):
    """A locally computed product: an inventory node that is also callable.

    Inheriting from ParameterIndex is what lets a single object sit in the inventory tree,
    be passed straight to speasy.get_data() and be called like the function it wraps.
    """

    def __init__(self, name: str, provider: str, uid: str, callback: Callable,
                 meta: Optional[dict] = None):
        super().__init__(name=name, provider=provider, uid=uid, meta=meta)
        self.__spz_callback__ = callback

    def __call__(self, start_time, stop_time):
        return self.__spz_callback__(start_time, stop_time)


def _make_virtual_product_node(parent: SpeasyIndex, name: str, uid: str,
                               callback: Callable) -> VirtualProduct:
    """Attach a VirtualProduct leaf under parent, replacing any existing one, and return it.

    Counterpart of make_inventory_node, which can't be used here:
    - it can't pass the callback to VirtualProduct;
    - it returns an existing leaf untouched, so on re-registration the tree node would
      still call the old callback while _callbacks (used by get_data) holds the new one.
      Replacing the leaf keeps both in sync.
    """
    node = VirtualProduct(name=name, provider='virtual', uid=uid, callback=callback)
    parent.__dict__[name] = node
    return node


def _register(product_uid: str, callback: Callable) -> VirtualProduct:
    """Serve callback(start_time, stop_time) as the product 'virtual/<product_uid>'.

    Internal on purpose: the public registration API, which takes a full path and
    returns a callable handle, comes with the decorator.
    Returns the tree leaf, a VirtualProduct wrapping callback.
    """
    _callbacks[product_uid] = callback

    *folders, leaf = product_uid.split('/')
    parent = _root
    for name in folders:
        parent = make_inventory_node(parent, SpeasyIndex, name, 'virtual', name)
    node = _make_virtual_product_node(parent, leaf, product_uid, callback)
    _flat_inventory.parameters[product_uid] = node
    return node


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
