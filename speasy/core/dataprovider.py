import logging
from datetime import datetime, timezone
from functools import wraps
from threading import Lock
from typing import Callable, Dict, List, Optional, Tuple

from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory import ProviderInventory
from speasy.core.inventory.indexes import (DatasetIndex, ParameterIndex,
                                           SpeasyIndex, inventory_has_changed)
from speasy.core.proxy import GetInventory, Proxyfiable, MINIMUM_REQUIRED_PROXY_VERSION
from speasy.inventories import flat_inventories, tree

log = logging.getLogger(__name__)
GET_DATA_ALLOWED_KWARGS = ['product', 'start_time', 'stop_time', 'extra_http_headers', 'progress']
PROVIDERS = {}
# every main and alternative provider name -> provider class, filled by register_provider
_PROVIDER_CLASSES: Dict[str, type] = {}


def register_provider(cls):
    """Class decorator making a data provider known to Speasy under its ``PROVIDER_NAME`` and
    ``PROVIDER_ALT_NAMES`` class attributes. Atomic: on a name clash nothing is registered."""
    if not getattr(cls, "PROVIDER_NAME", None):
        raise ValueError(f"Can't register {cls.__name__}: it has no PROVIDER_NAME")
    # get_data lowercases the provider of an index (provider_and_product), so it only finds lowercase main names
    if cls.PROVIDER_NAME != cls.PROVIDER_NAME.lower():
        raise ValueError(f"Can't register {cls.__name__}: PROVIDER_NAME {cls.PROVIDER_NAME!r} must be lowercase")
    names = [cls.PROVIDER_NAME, *cls.PROVIDER_ALT_NAMES]
    if taken := [name for name in names if name in _PROVIDER_CLASSES]:
        raise ValueError(f"Can't register {cls.__name__}: provider name(s) {taken} already taken")
    _PROVIDER_CLASSES.update(dict.fromkeys(names, cls))
    return cls


def registered_providers() -> Dict[str, type]:
    """Main name -> provider class, in registration order, which is also the init order."""
    return {cls.PROVIDER_NAME: cls for cls in _PROVIDER_CLASSES.values()}


def main_provider_name(name: str) -> Optional[str]:
    cls = _PROVIDER_CLASSES.get(name)
    return cls.PROVIDER_NAME if cls is not None else None


def provider_names(main_name: str) -> List[str]:
    cls = _PROVIDER_CLASSES[main_name]
    return [cls.PROVIDER_NAME, *cls.PROVIDER_ALT_NAMES]


class ParameterRangeCheck(object):
    def __init__(self):
        pass

    def __call__(self, get_data: Callable):
        @wraps(get_data)
        def wrapped(wrapped_self, product, start_time, stop_time, **kwargs):
            p_range = wrapped_self.parameter_range(product)
            if not p_range.intersect(DateTimeRange(start_time, stop_time)):
                log.warning(f"You are requesting {product} outside of its definition range {p_range}")
                return None
            return get_data(wrapped_self, product=product, start_time=start_time, stop_time=stop_time, **kwargs)

        return wrapped


def _get_inventory_args(provider_name, **kwargs):
    return {'provider': f"{provider_name}"}


class DataProvider:
    """Base class for all data providers.

    A provider declares its names as class attributes and registers itself with
    :func:`register_provider`, which is all Speasy needs to route requests to it.

    Parameters
    ----------
    provider_name: str or None
        The name of the data provider. Defaults to the ``PROVIDER_NAME`` class attribute,
        and must match it when both are given.
    provider_alt_names: List or None
        Alternative names for the data provider, also used to register the provider's inventory as
        valid aliases. Defaults to the ``PROVIDER_ALT_NAMES`` class attribute, and must match it when
        both are given.
    inventory_disable_proxy: bool
        If True, the inventory will be fetched directly from the provider, bypassing any proxy settings.
    min_proxy_version: str
        Minimum required version of the proxy server to use for fetching the inventory.
    """
    PROVIDER_NAME: Optional[str] = None
    PROVIDER_ALT_NAMES: Tuple[str, ...] = ()

    def __init__(self, provider_name: Optional[str] = None, provider_alt_names: Optional[List[str]] = None,
                 inventory_disable_proxy=False, min_proxy_version=MINIMUM_REQUIRED_PROXY_VERSION):
        self.provider_name, self.provider_alt_names = self._resolve_names(provider_name, provider_alt_names)
        self._inventory_disable_proxy = inventory_disable_proxy
        self.flat_inventory = ProviderInventory()
        self.min_proxy_version = min_proxy_version
        flat_inventories.__dict__[self.provider_name] = self.flat_inventory
        for alt_name in self.provider_alt_names:
            flat_inventories.__dict__[alt_name] = self.flat_inventory
        self.update_inventory()
        PROVIDERS[self.provider_name] = self

    @classmethod
    def _resolve_names(cls, provider_name, provider_alt_names) -> Tuple[str, List[str]]:
        if cls.PROVIDER_NAME is None:
            if provider_name is None:
                raise TypeError(f"{cls.__name__} needs a provider_name argument or a PROVIDER_NAME class attribute")
            return provider_name, list(provider_alt_names or [])
        declared = (cls.PROVIDER_NAME, list(cls.PROVIDER_ALT_NAMES))
        given = (provider_name or cls.PROVIDER_NAME,
                 list(cls.PROVIDER_ALT_NAMES if provider_alt_names is None else provider_alt_names))
        if given != declared:
            raise ValueError(f"{cls.__name__} declares its names as {declared}, but was given {given}")
        return declared

    def build_inventory(self, root: SpeasyIndex) -> SpeasyIndex:
        """Override this method to build the inventory tree from the public inventory source."""
        raise NotImplementedError("You need to implement the build_inventory method in your DataProvider subclass.")

    @Proxyfiable(request=GetInventory, arg_builder=_get_inventory_args)
    def _inventory(self, provider_name) -> SpeasyIndex:
        return self.build_inventory(SpeasyIndex(provider=provider_name, name=provider_name, uid=provider_name,
                                                meta={'build_date': datetime.now(tz=timezone.utc).isoformat()}))

    def build_private_inventory(self, root: SpeasyIndex) -> SpeasyIndex:
        """Override this method to add private inventory items that are not fetched from the public inventory source."""
        return root

    def _update_private_inventory(self, root: SpeasyIndex):
        return self.build_private_inventory(root)

    def update_inventory(self):
        lock = Lock()
        with lock:
            new_inventory = self._inventory(provider_name=self.provider_name,
                                            disable_proxy=self._inventory_disable_proxy,
                                            min_proxy_version=self.min_proxy_version)
            if inventory_has_changed(tree.__dict__.get(self.provider_name, SpeasyIndex("", "", "")), new_inventory):
                if self.provider_name in tree.__dict__:
                    tree.__dict__[self.provider_name].clear()
                tree.__dict__[self.provider_name] = new_inventory
            self._update_private_inventory(tree.__dict__[self.provider_name])
            self.flat_inventory.clear()
            self.flat_inventory.update(tree.__dict__[self.provider_name])

    def _to_dataset_index(self, index_or_str) -> DatasetIndex:
        if type(index_or_str) is str:
            if index_or_str in self.flat_inventory.datasets:
                return self.flat_inventory.datasets[index_or_str]
            else:
                raise ValueError(f"Unknown dataset: {index_or_str}")

        if isinstance(index_or_str, DatasetIndex):
            return index_or_str
        else:
            raise TypeError(f"given dataset {index_or_str} of type {type(index_or_str)} is not a compatible index")

    def _to_parameter_index(self, index_or_str) -> ParameterIndex:
        if type(index_or_str) is str:
            if index_or_str in self.flat_inventory.parameters:
                return self.flat_inventory.parameters[index_or_str]
            else:
                if index_or_str in self.flat_inventory.datasets:
                    raise ValueError(
                        f"Can't directly download a whole dataset from {self.provider_name}, you need to download each parameter separately.")
                else:
                    raise ValueError(f"Unknown parameter: {index_or_str}")

        if isinstance(index_or_str, ParameterIndex):
            return index_or_str
        else:
            raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")

    def _parameter_range(self, parameter_id: str or ParameterIndex) -> Optional[DateTimeRange]:
        parameter = self._to_parameter_index(parameter_id)
        return DateTimeRange(
            parameter.start_date,
            parameter.stop_date
        )

    def _dataset_range(self, dataset_id: str or DatasetIndex) -> Optional[DateTimeRange]:
        ds = self._to_dataset_index(dataset_id)
        return DateTimeRange(
            ds.start_date,
            ds.stop_date
        )
