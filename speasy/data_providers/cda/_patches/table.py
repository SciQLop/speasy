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


def _flattened(dataset: str, time: str, names: tuple[str, ...]) -> tuple[PatchedParameter, ...]:
    """Each `<variable>_f` product flattens the file variable `<variable>`, timed by the 2D `time` variable."""
    return tuple(PatchedParameter(dataset, name, name.removesuffix('_f'), TimeMatrix(time=time)) for name in names)


def _dbm(dataset: str, time_prefix: str, *channels: str) -> tuple[PatchedParameter, ...]:
    return _flattened(f'PSP_FLD_L2_DFB_DBM_{dataset}', f'psp_fld_l2_dfb_dbm_{time_prefix}_time_series_TT2000',
                      tuple(f'psp_fld_l2_dfb_dbm_{channel}_f' for channel in channels))


_TDS = 'PSP_FLD_L2_TDS_WF_Burst_Time_Series_'

PSP_FIELDS = (
    _dbm('VAC', 'vac', *(f'vac{i}' for i in range(1, 6)))
    + _dbm('VDC', 'vdc', *(f'vdc{i}' for i in range(1, 6)))
    + _dbm('DVAC', 'dvac', 'dvac12', 'dvac34', 'dvacz')
    + _dbm('DVDC', 'dvdc', 'dvdc12', 'dvdc34', 'dvdcz')
    + _dbm('SCM', 'scmlg', 'scmlgu', 'scmlgv', 'scmlgw')
    + _dbm('SCM', 'scmhg', 'scmhgu', 'scmhgv', 'scmhgw')
    + _flattened('PSP_FLD_L2_TDS_WF', f'{_TDS}Times_TT2000', tuple(f'{_TDS}{name}_f' for name in (
        'V1_Engineering_mV', 'V2_Engineering_mV', 'V3_Engineering_mV', 'V4_Engineering_mV', 'V5_Engineering_mV',
        'V1V2_Engineering_mV', 'V3V4_Engineering_mV', 'V1234_Engineering_mV',
        'SCM4_Engineering_nT', 'SCM5_Engineering_nT', 'SCM4_Engineering_mV', 'SCM5_Engineering_mV',
        'SWEAP_Counts')))
)

PATCHES: tuple[PatchedParameter, ...] = PSP_FIELDS
INJECTED: tuple[InjectedDataset, ...] = ()


def patch_for(dataset: str, name: str) -> Optional[PatchedParameter]:
    # Rebuilt per call (the table is tiny) so that tests can swap PATCHES.
    return {(p.dataset, p.name): p for p in PATCHES}.get((dataset, name))


def is_injected(dataset: str) -> bool:
    return any(d.id == dataset for d in INJECTED)
