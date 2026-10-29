"""Virtual products: products computed locally instead of fetched from a web service."""

import difflib
import threading
import warnings
from typing import Callable, Optional

from ..core.algorithms import fix_name
from ..core.dataprovider import register_provider
from ..core.inventory import ProviderInventory
from ..core.inventory.indexes import ParameterIndex, SpeasyIndex, make_inventory_node
from ..inventories import tree, flat_inventories
from ..products.variable import SpeasyVariable

_root = SpeasyIndex(name="virtual", provider="virtual", uid="virtual")
_flat_inventory = ProviderInventory()
_MAX_DEPTH = 128
_registration_lock = threading.Lock()


class _Resolution(threading.local):
    """Paths of the virtual products being computed, outermost first; one list per thread."""

    def __init__(self):
        self.chain = []


_resolution = _Resolution()


def _path_to_uid(path: str) -> str:
    """Turn the public path 'virtual/plasma/beta' into the registry uid 'plasma/beta'.

    Empty or blank segments (from //, / / or a trailing /) are dropped; the rest is kept as is.
    """
    if not isinstance(path, str):
        raise TypeError(f"virtual product path must be a str, got {type(path).__name__}")
    provider, _, rest = path.partition('/')
    if provider != 'virtual' or not rest:
        raise ValueError(f"virtual product path must look like 'virtual/<path>', got {path!r}")
    uid = '/'.join(seg for seg in rest.split('/') if seg.strip())
    if not uid:
        raise ValueError(f"virtual product path must look like 'virtual/<path>', got {path!r}")
    return uid


def _call_checked(product_uid: str, callback: Callable, start_time, stop_time,
                  labels: Optional[list] = None, meta: Optional[dict] = None):
    """Call callback(start_time, stop_time) and check it returned a SpeasyVariable or None.

    Shared by both ways of reaching a virtual product: calling the VirtualProduct
    directly, and speasy.get_data() through _VirtualProvider. Also guards against
    virtual products requesting each other endlessly.
    """
    chain = _resolution.chain
    chain.append(f"virtual/{product_uid}")
    try:
        if len(chain) > _MAX_DEPTH:
            raise VirtualProductCycleError(f"Virtual product chain deeper than {_MAX_DEPTH} levels, "
                                           f"probably a cycle: {' -> '.join(chain)}")
        result = callback(start_time, stop_time)
    finally:
        chain.pop()
    if result is not None and not isinstance(result, SpeasyVariable):
        raise VirtualProductTypeError(f"Virtual product 'virtual/{product_uid}': "
                                      f"{getattr(callback, '__qualname__', callback)} returned "
                                      f"{type(result).__name__}, expected SpeasyVariable or None")
    if result is not None and labels is not None:
        result = result.with_labels(labels)
    if result is not None and meta is not None:
        # keys are uppercased to match ISTP convention (e.g. "units" -> "UNITS")
        result = result.with_meta({k.upper(): v for k, v in meta.items()})
    return result


class VirtualProduct(ParameterIndex):
    """A locally computed product: an inventory node that is also callable.

    Inheriting from ParameterIndex is what lets a single object sit in the inventory tree,
    be passed straight to speasy.get_data() and be called like the function it wraps.
    """

    def __init__(self, name: str, provider: str, uid: str, callback: Callable,
                 meta: Optional[dict] = None, labels: Optional[list] = None):
        super().__init__(name=name, provider=provider, uid=uid, meta=meta)
        self.__spz_callback__ = callback
        self.__spz_labels__ = labels
        self.__spz_meta__ = meta

    def __call__(self, start_time, stop_time):
        return _call_checked(self.spz_uid(), self.__spz_callback__, start_time, stop_time,
                             labels=self.__spz_labels__, meta=self.__spz_meta__)


def _register(product_uid: str, callback: Callable, meta: Optional[dict] = None,
              labels: Optional[list] = None) -> VirtualProduct:
    """Serve callback(start_time, stop_time) as the product 'virtual/<product_uid>'.

    Internal — use register_virtual_product() for the public API.
    Returns the tree leaf, a VirtualProduct wrapping callback.
    """
    with _registration_lock:
        return _register_locked(product_uid, callback, meta, labels)


def _register_locked(product_uid: str, callback: Callable, meta: Optional[dict],
                     labels: Optional[list]) -> VirtualProduct:
    previous = _flat_inventory.parameters.get(product_uid)
    if previous is not None:
        previous = previous.__spz_callback__
        warnings.warn(f"Re-registering 'virtual/{product_uid}': "
                      f"{getattr(previous, '__qualname__', previous)} is replaced by "
                      f"{getattr(callback, '__qualname__', callback)}",
                      stacklevel=4)

    *folders, leaf = [fix_name(seg) for seg in product_uid.split('/')]
    parent = _root
    for name in folders:
        parent = make_inventory_node(parent, SpeasyIndex, name, 'virtual', name)
    existing = parent.__dict__.get(leaf)
    if isinstance(existing, VirtualProduct) and existing.spz_uid() != product_uid:
        warnings.warn(f"'virtual/{product_uid}' and 'virtual/{existing.spz_uid()}' share the tree name "
                      f"'{leaf}': the tree now shows 'virtual/{product_uid}' only",
                      stacklevel=4)
    node = make_inventory_node(parent, VirtualProduct, leaf, 'virtual', product_uid,
                               extra_args={"callback": callback, "labels": labels},
                               force=True, **(meta or {}))
    _flat_inventory.parameters[product_uid] = node
    return node


def register_virtual_product(path: str, *args: Callable, meta: Optional[dict] = None,
                              labels: Optional[list] = None):
    """Serve a callback(start_time, stop_time) as the product at path, e.g. 'virtual/plasma/beta'.

    Two call forms:
    - register_virtual_product(path, callback) registers callback and returns the tree leaf;
    - @register_virtual_product(path) does the same as a decorator.
    The tree leaf stays callable and can be passed straight to speasy.get_data().
    meta, if given, becomes attributes of the tree leaf: meta={"units": "nT"} gives leaf.units.
    labels, if given, overrides the column names of the returned SpeasyVariable.
    """
    uid = _path_to_uid(path)
    if args:
        return _register(uid, args[0], meta, labels)

    def decorator(callback: Callable) -> VirtualProduct:
        return _register(uid, callback, meta, labels)

    return decorator


class UnknownVirtualProduct(ValueError):
    """Raised when a virtual product is requested but was never registered."""


class VirtualProductTypeError(TypeError):
    """Raised when a virtual product callback returns something other than a SpeasyVariable or None."""


class VirtualProductCycleError(RecursionError):
    """Raised when virtual products request each other more than _MAX_DEPTH levels deep, usually a cycle."""


@register_provider
class _VirtualProvider:
    """Serves virtual products as a registered provider, started by the dispatcher on first use.

    Deliberately not a DataProvider subclass: get_data() is the whole contract the
    dispatcher needs, while DataProvider.__init__ would fetch an inventory through
    the proxy for products that are local by definition.
    """
    NAME = 'virtual'
    ALIASES = ()
    provider_name = NAME

    def get_data(self, product_uid: str, start_time, stop_time, **kwargs):
        # One lookup: the node holds the callback, labels and meta of a single registration.
        node = _flat_inventory.parameters.get(product_uid)
        if node is None:
            raise UnknownVirtualProduct(_unknown_product_message(product_uid))
        return node(start_time, stop_time)


def _unknown_product_message(product_uid: str) -> str:
    with _registration_lock:
        known_uids = list(_flat_inventory.parameters)
    message = f"Unknown virtual product 'virtual/{product_uid}'"
    close_uids = difflib.get_close_matches(product_uid, known_uids, n=3)
    if close_uids:
        message += ". Did you mean " + ", ".join(f"'virtual/{uid}'" for uid in close_uids) + "?"
    return message


def _init_virtual_provider():
    """Plug the virtual products inventory into speasy's inventory trees."""
    tree.__dict__['virtual'] = _root
    flat_inventories.__dict__['virtual'] = _flat_inventory

_init_virtual_provider()
