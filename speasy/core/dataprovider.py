import logging
from datetime import datetime
from functools import wraps
from threading import Lock
from typing import Callable, List, Optional

from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory import ProviderInventory
from speasy.core.inventory.indexes import (DatasetIndex, ParameterIndex,
                                           SpeasyIndex, inventory_has_changed)
from speasy.core.proxy import GetInventory, Proxyfiable
from speasy.inventories import flat_inventories, tree

log = logging.getLogger(__name__)
GET_DATA_ALLOWED_KWARGS = ['product', 'start_time', 'stop_time', 'extra_http_headers', 'progress']
PROVIDERS = {}


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
    def __init__(self, provider_name: str, provider_alt_names: List or None = None, inventory_disable_proxy=False):
        self.provider_name = provider_name
        self._inventory_disable_proxy = inventory_disable_proxy
        self.provider_alt_names = provider_alt_names or []
        self.flat_inventory = ProviderInventory()
        flat_inventories.__dict__[provider_name] = self.flat_inventory
        for alt_name in self.provider_alt_names:
            flat_inventories.__dict__[alt_name] = self.flat_inventory
        self.update_inventory()
        PROVIDERS[provider_name] = self

    @Proxyfiable(request=GetInventory, arg_builder=_get_inventory_args)
    def _inventory(self, provider_name) -> SpeasyIndex:
        return self.build_inventory(SpeasyIndex(provider=provider_name, name=provider_name, uid=provider_name,
                                                meta={'build_date': datetime.utcnow().isoformat()}))

    def _update_private_inventory(self, root: SpeasyIndex):
        if hasattr(self, 'build_private_inventory'):
            return self.build_private_inventory(root)

    def update_inventory(self):
        lock = Lock()
        with lock:
            new_inventory = self._inventory(provider_name=self.provider_name,
                                            disable_proxy=self._inventory_disable_proxy)
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
