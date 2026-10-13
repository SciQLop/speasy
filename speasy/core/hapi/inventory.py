"""Pure HAPI JSON → Speasy inventory tree builder (no network access).

See https://github.com/hapi-server/data-specification/blob/master/hapi-3.3.0/HAPI-data-access-spec-3.3.0.md
"""
from typing import Callable, Iterable, List, Mapping

from speasy.core import fix_name
from speasy.core.inventory.indexes import DatasetIndex, ParameterIndex, SpeasyIndex

_NOT_DATASET_META = ('HAPI', 'status', 'parameters')


def build_inventory(root: SpeasyIndex, server_meta: Mapping, catalog: Iterable[Mapping]) -> SpeasyIndex:
    """Fills ``root`` with one node per catalog entry.

    ``catalog`` has the shape of ``/catalog?depth=all``: ``{"id", "title", "info"?}`` entries, where ``info`` is the
    ``/info`` response for that dataset. Entries without ``info`` become datasets holding only their title.
    """
    root.__dict__.update(server_meta)
    for entry in catalog:
        _add_dataset(root, entry)
    return root


def _add_dataset(root: SpeasyIndex, entry: Mapping) -> None:
    provider = root.spz_provider()
    *folders, name = _segments(entry['id'])
    parent = root
    for depth, segment in enumerate(folders, start=1):
        parent = _folder(parent, '/'.join(folders[:depth]), segment)
    meta = _dataset_meta(entry)
    dataset = _new_child(parent, name, lambda n: DatasetIndex(name=n, provider=provider, uid=entry['id'], meta=meta))
    for parameter in _data_parameters(entry):
        _add_parameter(dataset, parameter)


def _add_parameter(dataset: DatasetIndex, parameter: Mapping) -> None:
    meta = {**parameter, 'start_date': dataset.__dict__.get('start_date'),
            'stop_date': dataset.__dict__.get('stop_date')}
    uid = f"{dataset.spz_uid()}/{parameter['name']}"
    _new_child(dataset, parameter['name'],
               lambda n: ParameterIndex(name=n, provider=dataset.spz_provider(), uid=uid, meta=meta))


def _segments(dataset_id: str) -> List[str]:
    return [s for s in dataset_id.split('/') if s] or [dataset_id]


def _dataset_meta(entry: Mapping) -> dict:
    info = {k: v for k, v in entry.get('info', {}).items() if k not in _NOT_DATASET_META}
    meta = {**{k: v for k, v in entry.items() if k not in ('id', 'info')}, **info}
    if 'title' in meta:
        meta.setdefault('description', meta['title'])
    if 'startDate' in info:
        meta.update(start_date=info['startDate'], stop_date=info['stopDate'])
    return meta


def _data_parameters(entry: Mapping) -> List[Mapping]:
    """``parameters[0]`` is always the time column."""
    return entry.get('info', {}).get('parameters', [])[1:]


def _folder(parent: SpeasyIndex, uid: str, segment: str) -> SpeasyIndex:
    return _child(parent, segment,
                  matches=lambda node: type(node) is SpeasyIndex and node.spz_uid() == uid,
                  make=lambda n: SpeasyIndex(name=n, provider=parent.spz_provider(), uid=uid))


def _new_child(parent: SpeasyIndex, raw_name: str, make: Callable[[str], SpeasyIndex]) -> SpeasyIndex:
    return _child(parent, raw_name, matches=lambda _: False, make=make)


def _child(parent: SpeasyIndex, raw_name: str, matches: Callable, make: Callable[[str], SpeasyIndex]) -> SpeasyIndex:
    """Different raw names can share a ``fix_name``, or clash with a metadata field: suffix with ``_`` until free."""
    name = fix_name(raw_name) or '_'
    while name in parent.__dict__:
        if matches(parent.__dict__[name]):
            return parent.__dict__[name]
        name += '_'
    parent.__dict__[name] = make(name)
    return parent.__dict__[name]
