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

_SOLO_RPW = 'https://cdaweb.gsfc.nasa.gov/pub/data/solar-orbiter/rpw/science/l2'
_MASTERS = 'https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS'
_TDS_KINDS = {'RSWF': 'rapid', 'TSWF': 'regular'}
_TDS_BANDS = {'B': 'magnetic', 'E': 'electric'}


def _solo_rpw_dataset(id: str, folder: str, description: str) -> InjectedDataset:
    return InjectedDataset(
        id=id, sibling_of='SOLO_L2_RPW-TDS-SURV-HIST2D',
        filenaming=f'solo_l2_rpw-{folder}_%Y%m%d_%Q.cdf', url=f'{_SOLO_RPW}/{folder}', subdividedby='%Y',
        mastercdf=f'{_MASTERS}/solo_l2_rpw-{folder}_00000000_v01.cdf', start_date='2020-06-15 00:00:00',
        description=f'Solar Orbiter, Level 2, Radio and Plasma Waves, {description} - M.Maksimovic (CNRS, LIRA '
                    f'Observatoire de Paris-PSL)')


def _solo_tds_dataset(kind: str, band: str) -> InjectedDataset:
    return _solo_rpw_dataset(
        f'SOLO_L2_RPW-TDS-SURV-{kind}-{band}', f'tds-surv-{kind.lower()}-{band.lower()}',
        f'Time Domain Sampler, {_TDS_KINDS[kind]} waveform snapshots, {_TDS_BANDS[band]} component, survey')


def _solo_tds_electric(kind: str) -> tuple[PatchedParameter, ...]:
    dataset = f'SOLO_L2_RPW-TDS-SURV-{kind}-E'
    decoder = EpochPlusOffsets(offsets='EPOCH_OFFSET', ns_per_unit=1.0, sample_axis=2)
    return tuple(PatchedParameter(dataset, name, name, decoder, {'UNITS': units, 'spz_shape': 3})
                 for name, units in (('WAVEFORM_DATA', 'V/m'), ('WAVEFORM_DATA_VOLTAGE', 'V')))


def _solo_tds_magnetic(kind: str) -> tuple[PatchedParameter, ...]:
    """The -B files carry no EPOCH_OFFSET: each snapshot's samples are evenly spaced at its own SAMPLING_RATE."""
    decoder = EpochPlusSamplingRate(rate='SAMPLING_RATE')
    return (PatchedParameter(f'SOLO_L2_RPW-TDS-SURV-{kind}-B', 'B', 'B', decoder, {'UNITS': 'nT'}),)


SOLO_RPW_TDS = tuple(p for kind in _TDS_KINDS for p in _solo_tds_electric(kind) + _solo_tds_magnetic(kind))

_LFR_RATES_HZ = {'F0': 24576, 'F1': 4096, 'F2': 256}
_LFR_SWF = {  # band: (sample axis, {variable: units})
    'E': (1, {'VDC': 'V', 'EDC': 'V', 'EAC': 'V'}),
    'B': (2, {'B': 'nT', 'B_RTN': 'nT'}),
}


def _solo_lfr_dataset(band: str) -> InjectedDataset:
    return _solo_rpw_dataset(f'SOLO_L2_RPW-LFR-SURV-SWF-{band}', f'lfr-surv-swf-{band.lower()}',
                             f'Low Frequency Receiver, waveform snapshots, {_TDS_BANDS[band]} component, survey')


def _solo_lfr_split(band: str) -> tuple[PatchedParameter, ...]:
    """Each snapshot is sampled at one of the LFR rates; `<variable>_F0/_F1/_F2` keep the snapshots of one rate."""
    sample_axis, variables = _LFR_SWF[band]
    return tuple(
        PatchedParameter(f'SOLO_L2_RPW-LFR-SURV-SWF-{band}', f'{variable}_{name}', variable,
                         EpochPlusSamplingRate(rate='SAMPLING_RATE', rate_hz=rate_hz, sample_axis=sample_axis),
                         {'UNITS': units, 'spz_shape': 3})
        for variable, units in variables.items() for name, rate_hz in _LFR_RATES_HZ.items())


SOLO_RPW_LFR = tuple(p for band in _LFR_SWF for p in _solo_lfr_split(band))

_RBSP_WFR = ('BuSamples', 'BvSamples', 'BwSamples', 'EuSamples', 'EvSamples', 'EwSamples')
_RBSP_WFR_DATASETS = tuple(f'RBSP-{probe}_WFR-WAVEFORM{kind}_EMFISIS-L2'
                           for probe in 'AB' for kind in ('', '-CONTINUOUS-BURST'))
_RBSP_HFR_DATASETS = tuple(f'RBSP-{probe}_HFR-WAVEFORM_EMFISIS-L2' for probe in 'AB')
_TRACERS = {'TS1_L2_MSC_BAC': 'ts1_l2_bac_tscs', 'TS2_L2_MSC_BAC': 'ts2_l2_bac_tscs'}


def _bucket_waveforms(datasets: tuple[str, ...], names: tuple[str, ...], decoder: EpochPlusOffsets,
                      variable: Optional[str] = None, components: int = 1) -> tuple[PatchedParameter, ...]:
    """One decoder for every `name` of every dataset; `variable` is the file variable when it differs from `name`."""
    return tuple(PatchedParameter(dataset, name, variable or name, decoder, {'spz_shape': components})
                 for dataset in datasets for name in names)


RBSP_EMFISIS = (
    _bucket_waveforms(_RBSP_WFR_DATASETS, _RBSP_WFR, EpochPlusOffsets(offsets='timeOffsets', ns_per_unit=1.0))
    # Data files hold `HFRsamples` and `timeOffsets`; `HFRsamples_spec` and `timeOffsets_extended` exist only in the master.
    + _bucket_waveforms(_RBSP_HFR_DATASETS, ('HFRsamples_spec',),
                        EpochPlusOffsets(offsets='timeOffsets', ns_per_unit=1.0), variable='HFRsamples')
)

TRACERS_BAC = tuple(p for dataset, name in _TRACERS.items() for p in _bucket_waveforms(
    (dataset,), (name,), EpochPlusOffsets(offsets='EpochOffset', ns_per_unit=1.0), components=3))

VOYAGER_PWS = _bucket_waveforms(('VG1_PWS_WF', 'VG2_PWS_WF'), ('Waveform',),
                                EpochPlusOffsets(offsets='timeOffsets', ns_per_unit=1000.0))

PATCHES: tuple[PatchedParameter, ...] = (
    PSP_FIELDS + SOLO_RPW_TDS + SOLO_RPW_LFR + RBSP_EMFISIS + TRACERS_BAC + VOYAGER_PWS)
INJECTED: tuple[InjectedDataset, ...] = (
    tuple(_solo_tds_dataset(kind, band) for kind in _TDS_KINDS for band in _TDS_BANDS)
    + tuple(_solo_lfr_dataset(band) for band in _LFR_SWF))


def patch_for(dataset: str, name: str) -> Optional[PatchedParameter]:
    # Rebuilt per call (the table is tiny) so that tests can swap PATCHES.
    return {(p.dataset, p.name): p for p in PATCHES}.get((dataset, name))


def is_injected(dataset: str) -> bool:
    return any(d.id == dataset for d in INJECTED)
