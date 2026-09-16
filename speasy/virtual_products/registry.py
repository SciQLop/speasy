"""Virtual products: products computed locally instead of fetched from a web service."""

import warnings
from typing import Callable, Dict, Optional

from ..core.inventory import ProviderInventory
from ..core.inventory.indexes import ParameterIndex, SpeasyIndex, make_inventory_node
from ..core.requests_scheduling.request_dispatch import PROVIDERS
from ..inventories import tree, flat_inventories
from ..products.variable import SpeasyVariable

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


def _call_checked(product_uid: str, callback: Callable, start_time, stop_time):
    """Call callback(start_time, stop_time) and check it returned a SpeasyVariable or None.

    Shared by both ways of reaching a virtual product: calling the VirtualProduct
    directly, and speasy.get_data() through _VirtualProvider.
    """
    result = callback(start_time, stop_time)
    if result is not None and not isinstance(result, SpeasyVariable):
        raise VirtualProductTypeError(f"Virtual product 'virtual/{product_uid}': "
                                      f"{getattr(callback, '__qualname__', callback)} returned "
                                      f"{type(result).__name__}, expected SpeasyVariable or None")
    return result


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
        return _call_checked(self.spz_uid(), self.__spz_callback__, start_time, stop_time)


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

    Internal — use register_virtual_product() for the public API.
    Returns the tree leaf, a VirtualProduct wrapping callback.
    """
    if product_uid in _callbacks:
        previous = _callbacks[product_uid]
        warnings.warn(f"Re-registering 'virtual/{product_uid}': "
                      f"{getattr(previous, '__qualname__', previous)} is replaced by "
                      f"{getattr(callback, '__qualname__', callback)}",
                      stacklevel=3)
    _callbacks[product_uid] = callback

    *folders, leaf = product_uid.split('/')
    parent = _root
    for name in folders:
        parent = make_inventory_node(parent, SpeasyIndex, name, 'virtual', name)
    node = _make_virtual_product_node(parent, leaf, product_uid, callback)
    _flat_inventory.parameters[product_uid] = node
    return node


def register_virtual_product(path: str, *args: Callable):
    """Serve a callback(start_time, stop_time) as the product at path, e.g. 'virtual/plasma/beta'.

    Two call forms:
    - register_virtual_product(path, callback) registers callback and returns the tree leaf;
    - @register_virtual_product(path) does the same as a decorator.
    The tree leaf stays callable and can be passed straight to speasy.get_data().
    """
    uid = _path_to_uid(path)
    if args:
        return _register(uid, args[0])

    def decorator(callback: Callable) -> VirtualProduct:
        return _register(uid, callback)

    return decorator


class UnknownVirtualProduct(ValueError):
    """Raised when a virtual product is requested but was never registered."""


class VirtualProductTypeError(TypeError):
    """Raised when a virtual product callback returns something other than a SpeasyVariable or None."""


class _VirtualProvider:
    """Serves virtual products through speasy's dispatch table.

    Deliberately not a DataProvider subclass: get_data() is the whole contract the
    dispatcher needs, while DataProvider.__init__ would fetch an inventory through
    the proxy for products that are local by definition.
    """

    def get_data(self, product_uid: str, start_time, stop_time, **kwargs):
        callback = _callbacks.get(product_uid)
        if callback is None:
            raise UnknownVirtualProduct(f"Unknown virtual product 'virtual/{product_uid}'")
        return _call_checked(product_uid, callback, start_time, stop_time)


def _init_virtual_provider():
    """Register the virtual provider in the dispatch table and its inventory."""
    PROVIDERS['virtual'] = _VirtualProvider()
    tree.__dict__['virtual'] = _root
    flat_inventories.__dict__['virtual'] = _flat_inventory

_init_virtual_provider()
