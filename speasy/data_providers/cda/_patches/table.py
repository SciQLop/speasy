"""Static table of CDAWeb dataset patches, consulted at read and inventory-load time."""
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Union

from .decoders import EpochPlusOffsets, EpochPlusSamplingRate, TimeMatrix


@dataclass(frozen=True)
class PatchedParameter:
    """`name` is the product name in the inventory, `variable` the one read from the file."""
    dataset: str
    name: str
    variable: str
    decoder: Union[TimeMatrix, EpochPlusOffsets, EpochPlusSamplingRate]
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InjectedDataset:
    """A dataset missing from CDAWeb's inventory, placed in the parent node of the `sibling_of` dataset."""
    id: str
    sibling_of: str
    filenaming: str
    url: str
    subdividedby: str
    mastercdf: str
    start_date: str
    description: str


PATCHES: tuple[PatchedParameter, ...] = ()
INJECTED: tuple[InjectedDataset, ...] = ()


def patch_for(dataset: str, name: str) -> Optional[PatchedParameter]:
    # Rebuilt per call (the table is tiny) so that tests can swap PATCHES.
    return {(p.dataset, p.name): p for p in PATCHES}.get((dataset, name))


def is_injected(dataset: str) -> bool:
    return any(d.id == dataset for d in INJECTED)
