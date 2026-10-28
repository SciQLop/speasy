"""Applies the patch table to a CDA inventory tree, every time one is loaded (built locally or downloaded)."""
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Dict, Iterator, Tuple

from speasy.core import fix_name
from speasy.core.inventory.indexes import DatasetIndex, ParameterIndex, SpeasyIndex
from speasy.data_providers.cda._inventory_builder._xml_catalogs_parser import alias_rules

from . import table
from .table import InjectedDataset, PatchedParameter

log = logging.getLogger(__name__)

_Located = Tuple[SpeasyIndex, DatasetIndex]


def _datasets_with_parent(node: SpeasyIndex) -> Iterator[_Located]:
    for child in node.__dict__.values():
        if isinstance(child, DatasetIndex):
            yield node, child
        elif isinstance(child, SpeasyIndex):
            yield from _datasets_with_parent(child)


def _datasets_by_uid(root: SpeasyIndex) -> Dict[str, _Located]:
    return {dataset.spz_uid(): (parent, dataset) for parent, dataset in _datasets_with_parent(root)}


def _injected_meta(entry: InjectedDataset, now: datetime) -> dict:
    meta = {key: value for key, value in asdict(entry).items() if key not in ('id', 'sibling_of')}
    return {**meta, 'serviceprovider_ID': entry.id, 'stop_date': now.isoformat()}


def _inject_dataset(parent: SpeasyIndex, entry: InjectedDataset, now: datetime):
    name = fix_name(alias_rules(entry.id))
    dataset = parent.__dict__.setdefault(name, DatasetIndex(name, 'cda', entry.id))
    dataset.__dict__.update(_injected_meta(entry, now))


def _inject_datasets(root: SpeasyIndex, now: datetime):
    datasets = _datasets_by_uid(root)
    for entry in table.INJECTED:
        # an already injected dataset (e.g. in a proxy inventory) is refreshed, so its stop date is this load's
        located = datasets.get(entry.id) or datasets.get(entry.sibling_of)
        if located is None:
            log.warning(f"Can't inject CDA dataset {entry.id}: its sibling {entry.sibling_of} is not in the inventory")
        else:
            _inject_dataset(located[0], entry, now)


def _parameter_meta(dataset: DatasetIndex, entry: PatchedParameter) -> dict:
    return {'spz_shape': 1, 'start_date': dataset.start_date, 'stop_date': dataset.stop_date,
            'dataset': dataset.spz_uid(), **entry.meta}


def _upsert_parameter(dataset: DatasetIndex, entry: PatchedParameter):
    parameter = dataset.__dict__.setdefault(fix_name(entry.name),
                                            ParameterIndex(entry.name, 'cda', f'{entry.dataset}/{entry.name}'))
    parameter.__dict__.pop('VIRTUAL', None)
    parameter.__dict__.update(_parameter_meta(dataset, entry))


def _upsert_parameters(root: SpeasyIndex):
    datasets = _datasets_by_uid(root)
    for entry in table.PATCHES:
        if entry.dataset in datasets:
            _upsert_parameter(datasets[entry.dataset][1], entry)


def patch_inventory(root: SpeasyIndex, now: datetime) -> SpeasyIndex:
    """Idempotent: injected datasets first, so that their parameters find them."""
    _inject_datasets(root, now)
    _upsert_parameters(root)
    return root
