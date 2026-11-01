"""Static table of CDAWeb dataset patches, consulted at read and inventory-load time.

One `DatasetPatch` row per dataset and decoder: add a row to fix a dataset until CDAWeb serves it right.
"""
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .decoders import Decoder, EpochPlusOffsets, EpochPlusSamplingRate, TimeMatrix


@dataclass(frozen=True)
class PatchedParameter:
    """`name` is the product name in the inventory, `variable` the one read from the file."""
    dataset: str
    name: str
    variable: str
    decoder: Decoder
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DatasetPatch:
    """Products of `dataset` read with `decoder`; `products` maps each product name to its file variable."""
    dataset: str
    decoder: Decoder
    products: Mapping[str, str]
    meta: Mapping[str, Any] = field(default_factory=dict)

    def parameters(self) -> tuple[PatchedParameter, ...]:
        return tuple(PatchedParameter(self.dataset, name, variable, self.decoder, self.meta)
                     for name, variable in self.products.items())


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


def same(*variables: str) -> dict[str, str]:
    """Products named like their file variable."""
    return {variable: variable for variable in variables}


def flattened(*variables: str) -> dict[str, str]:
    """`<variable>_f` products, next to the bucketed `<variable>` CDAWeb already lists."""
    return {f'{variable}_f': variable for variable in variables}


_PSP_TDS = 'PSP_FLD_L2_TDS_WF_Burst_Time_Series_'
_SOLO_TDS_E = EpochPlusOffsets(offsets='EPOCH_OFFSET', ns_per_unit=1.0, sample_axis=2)
_SOLO_TDS_B = EpochPlusSamplingRate(rate='SAMPLING_RATE')  # -B files have no EPOCH_OFFSET


def _lfr(rate_hz: int, sample_axis: int) -> EpochPlusSamplingRate:
    """LFR snapshots come at one of three rates; each `_F0/_F1/_F2` product keeps the snapshots of one rate."""
    return EpochPlusSamplingRate(rate='SAMPLING_RATE', rate_hz=rate_hz, sample_axis=sample_axis)


_RBSP_OFFSETS = EpochPlusOffsets(offsets='timeOffsets', ns_per_unit=1.0)
_RBSP_WFR = same('BuSamples', 'BvSamples', 'BwSamples', 'EuSamples', 'EvSamples', 'EwSamples')
# Data files hold `HFRsamples`; `HFRsamples_spec` is the name the master gives it.
_RBSP_HFR = {'HFRsamples_spec': 'HFRsamples'}
_TRACERS_OFFSETS = EpochPlusOffsets(offsets='EpochOffset', ns_per_unit=1.0)
_VOYAGER_OFFSETS = EpochPlusOffsets(offsets='timeOffsets', ns_per_unit=1000.0)

TABLE: tuple[DatasetPatch, ...] = (
    DatasetPatch('PSP_FLD_L2_DFB_DBM_VAC', TimeMatrix('psp_fld_l2_dfb_dbm_vac_time_series_TT2000'),
                 flattened(*(f'psp_fld_l2_dfb_dbm_vac{i}' for i in range(1, 6)))),
    DatasetPatch('PSP_FLD_L2_DFB_DBM_VDC', TimeMatrix('psp_fld_l2_dfb_dbm_vdc_time_series_TT2000'),
                 flattened(*(f'psp_fld_l2_dfb_dbm_vdc{i}' for i in range(1, 6)))),
    DatasetPatch('PSP_FLD_L2_DFB_DBM_DVAC', TimeMatrix('psp_fld_l2_dfb_dbm_dvac_time_series_TT2000'),
                 flattened('psp_fld_l2_dfb_dbm_dvac12', 'psp_fld_l2_dfb_dbm_dvac34', 'psp_fld_l2_dfb_dbm_dvacz')),
    DatasetPatch('PSP_FLD_L2_DFB_DBM_DVDC', TimeMatrix('psp_fld_l2_dfb_dbm_dvdc_time_series_TT2000'),
                 flattened('psp_fld_l2_dfb_dbm_dvdc12', 'psp_fld_l2_dfb_dbm_dvdc34', 'psp_fld_l2_dfb_dbm_dvdcz')),
    DatasetPatch('PSP_FLD_L2_DFB_DBM_SCM', TimeMatrix('psp_fld_l2_dfb_dbm_scmlg_time_series_TT2000'),
                 flattened('psp_fld_l2_dfb_dbm_scmlgu', 'psp_fld_l2_dfb_dbm_scmlgv', 'psp_fld_l2_dfb_dbm_scmlgw')),
    DatasetPatch('PSP_FLD_L2_DFB_DBM_SCM', TimeMatrix('psp_fld_l2_dfb_dbm_scmhg_time_series_TT2000'),
                 flattened('psp_fld_l2_dfb_dbm_scmhgu', 'psp_fld_l2_dfb_dbm_scmhgv', 'psp_fld_l2_dfb_dbm_scmhgw')),
    DatasetPatch('PSP_FLD_L2_TDS_WF', TimeMatrix(f'{_PSP_TDS}Times_TT2000'),
                 flattened(*(_PSP_TDS + name for name in (
                     'V1_Engineering_mV', 'V2_Engineering_mV', 'V3_Engineering_mV', 'V4_Engineering_mV',
                     'V5_Engineering_mV', 'V1V2_Engineering_mV', 'V3V4_Engineering_mV', 'V1234_Engineering_mV',
                     'SCM4_Engineering_nT', 'SCM5_Engineering_nT', 'SCM4_Engineering_mV', 'SCM5_Engineering_mV',
                     'SWEAP_Counts')))),

    DatasetPatch('SOLO_L2_RPW-TDS-SURV-RSWF-E', _SOLO_TDS_E, same('WAVEFORM_DATA'), {'UNITS': 'V/m', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-TDS-SURV-RSWF-E', _SOLO_TDS_E, same('WAVEFORM_DATA_VOLTAGE'),
                 {'UNITS': 'V', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-TDS-SURV-RSWF-B', _SOLO_TDS_B, same('B'), {'UNITS': 'nT'}),
    DatasetPatch('SOLO_L2_RPW-TDS-SURV-TSWF-E', _SOLO_TDS_E, same('WAVEFORM_DATA'), {'UNITS': 'V/m', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-TDS-SURV-TSWF-E', _SOLO_TDS_E, same('WAVEFORM_DATA_VOLTAGE'),
                 {'UNITS': 'V', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-TDS-SURV-TSWF-B', _SOLO_TDS_B, same('B'), {'UNITS': 'nT'}),

    DatasetPatch('SOLO_L2_RPW-LFR-SURV-SWF-E', _lfr(24576, sample_axis=1),
                 {'VDC_F0': 'VDC', 'EDC_F0': 'EDC', 'EAC_F0': 'EAC'}, {'UNITS': 'V', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-LFR-SURV-SWF-E', _lfr(4096, sample_axis=1),
                 {'VDC_F1': 'VDC', 'EDC_F1': 'EDC', 'EAC_F1': 'EAC'}, {'UNITS': 'V', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-LFR-SURV-SWF-E', _lfr(256, sample_axis=1),
                 {'VDC_F2': 'VDC', 'EDC_F2': 'EDC', 'EAC_F2': 'EAC'}, {'UNITS': 'V', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-LFR-SURV-SWF-B', _lfr(24576, sample_axis=2),
                 {'B_F0': 'B', 'B_RTN_F0': 'B_RTN'}, {'UNITS': 'nT', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-LFR-SURV-SWF-B', _lfr(4096, sample_axis=2),
                 {'B_F1': 'B', 'B_RTN_F1': 'B_RTN'}, {'UNITS': 'nT', 'spz_shape': 3}),
    DatasetPatch('SOLO_L2_RPW-LFR-SURV-SWF-B', _lfr(256, sample_axis=2),
                 {'B_F2': 'B', 'B_RTN_F2': 'B_RTN'}, {'UNITS': 'nT', 'spz_shape': 3}),

    DatasetPatch('RBSP-A_WFR-WAVEFORM_EMFISIS-L2', _RBSP_OFFSETS, _RBSP_WFR, {'spz_shape': 1}),
    DatasetPatch('RBSP-A_WFR-WAVEFORM-CONTINUOUS-BURST_EMFISIS-L2', _RBSP_OFFSETS, _RBSP_WFR, {'spz_shape': 1}),
    DatasetPatch('RBSP-B_WFR-WAVEFORM_EMFISIS-L2', _RBSP_OFFSETS, _RBSP_WFR, {'spz_shape': 1}),
    DatasetPatch('RBSP-B_WFR-WAVEFORM-CONTINUOUS-BURST_EMFISIS-L2', _RBSP_OFFSETS, _RBSP_WFR, {'spz_shape': 1}),
    DatasetPatch('RBSP-A_HFR-WAVEFORM_EMFISIS-L2', _RBSP_OFFSETS, _RBSP_HFR, {'spz_shape': 1}),
    DatasetPatch('RBSP-B_HFR-WAVEFORM_EMFISIS-L2', _RBSP_OFFSETS, _RBSP_HFR, {'spz_shape': 1}),

    DatasetPatch('TS1_L2_MSC_BAC', _TRACERS_OFFSETS, same('ts1_l2_bac_tscs', 'ts1_l2_bac_fac'), {'spz_shape': 3}),
    DatasetPatch('TS2_L2_MSC_BAC', _TRACERS_OFFSETS, same('ts2_l2_bac_tscs', 'ts2_l2_bac_fac'), {'spz_shape': 3}),

    DatasetPatch('VG1_PWS_WF', _VOYAGER_OFFSETS, same('Waveform'), {'spz_shape': 1}),
    DatasetPatch('VG2_PWS_WF', _VOYAGER_OFFSETS, same('Waveform'), {'spz_shape': 1}),
)

PATCHES: tuple[PatchedParameter, ...] = tuple(p for row in TABLE for p in row.parameters())


def _solo_rpw_dataset(id: str, folder: str, description: str) -> InjectedDataset:
    return InjectedDataset(
        id=id, sibling_of='SOLO_L2_RPW-TDS-SURV-HIST2D',
        filenaming=f'solo_l2_rpw-{folder}_%Y%m%d_%Q.cdf',
        url=f'https://cdaweb.gsfc.nasa.gov/pub/data/solar-orbiter/rpw/science/l2/{folder}', subdividedby='%Y',
        mastercdf=f'https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/solo_l2_rpw-{folder}_00000000_v01.cdf',
        start_date='2020-06-15 00:00:00',
        description=f'Solar Orbiter, Level 2, Radio and Plasma Waves, {description} - M.Maksimovic (CNRS, LIRA '
                    f'Observatoire de Paris-PSL)')


INJECTED: tuple[InjectedDataset, ...] = (
    _solo_rpw_dataset('SOLO_L2_RPW-TDS-SURV-RSWF-E', 'tds-surv-rswf-e',
                      'Time Domain Sampler, rapid waveform snapshots, electric component, survey'),
    _solo_rpw_dataset('SOLO_L2_RPW-TDS-SURV-RSWF-B', 'tds-surv-rswf-b',
                      'Time Domain Sampler, rapid waveform snapshots, magnetic component, survey'),
    _solo_rpw_dataset('SOLO_L2_RPW-TDS-SURV-TSWF-E', 'tds-surv-tswf-e',
                      'Time Domain Sampler, regular waveform snapshots, electric component, survey'),
    _solo_rpw_dataset('SOLO_L2_RPW-TDS-SURV-TSWF-B', 'tds-surv-tswf-b',
                      'Time Domain Sampler, regular waveform snapshots, magnetic component, survey'),
    _solo_rpw_dataset('SOLO_L2_RPW-LFR-SURV-SWF-E', 'lfr-surv-swf-e',
                      'Low Frequency Receiver, waveform snapshots, electric component, survey'),
    _solo_rpw_dataset('SOLO_L2_RPW-LFR-SURV-SWF-B', 'lfr-surv-swf-b',
                      'Low Frequency Receiver, waveform snapshots, magnetic component, survey'),
)


def patch_for(dataset: str, name: str) -> Optional[PatchedParameter]:
    # Rebuilt per call (the table is tiny) so that tests can swap PATCHES.
    return {(p.dataset, p.name): p for p in PATCHES}.get((dataset, name))


def is_injected(dataset: str) -> bool:
    return any(d.id == dataset for d in INJECTED)
