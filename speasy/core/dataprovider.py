from speasy.inventories import flat_inventories, tree
from speasy.core.inventory import ProviderInventory
from speasy.core.inventory.indexes import SpeasyIndex, DatasetIndex, ParameterIndex, from_dict, to_dict
from speasy.core.datetime_range import DateTimeRange
from .cache import CacheCall
from ..config import inventories_cache_retention_days
from datetime import timedelta
from typing import List, Optional


class DataProvider:
    def __init__(self, provider_name: str, provider_alt_names: List or None = None):
        self.provider_name = provider_name
        self.provider_alt_names = provider_alt_names or []
        self.flat_inventory = ProviderInventory()
        flat_inventories.__dict__[provider_name] = self.flat_inventory
        tree.__dict__[provider_name] = from_dict(self._inventory(provider_name))
        for alt_name in self.provider_alt_names:
            flat_inventories.__dict__[alt_name] = self.flat_inventory

    @CacheCall(cache_retention=timedelta(days=int(inventories_cache_retention_days.get())), is_pure=True)
    def _inventory(self, provider_name):
        return to_dict(self.build_inventory(SpeasyIndex(provider=provider_name, name=provider_name, uid=provider_name)))

    def _to_dataset_index(self, index_or_str) -> DatasetIndex:
        if type(index_or_str) is str:
            if index_or_str in self.flat_inventory.datasets:
                return self.flat_inventory.datasets[index_or_str]
            else:
                raise ValueError(f"Unknown dataset: {index_or_str}")

        if type(index_or_str) is DatasetIndex:
            return index_or_str
        else:
            raise TypeError(f"given dataset {index_or_str} of type {type(index_or_str)} is not a compatible index")

    def _to_parameter_index(self, index_or_str) -> ParameterIndex:
        if type(index_or_str) is str:
            if index_or_str in self.flat_inventory.parameters:
                return self.flat_inventory.parameters[index_or_str]
            else:
                raise ValueError(f"Unknown parameter: {index_or_str}")

        if type(index_or_str) is ParameterIndex:
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
