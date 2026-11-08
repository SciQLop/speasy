import io
import logging
import tarfile
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

from packaging.version import Version

import numpy as np

from speasy.core import any_files, AllowedKwargs, fix_name, EnsureUTCDateTime, tap
from speasy.core.codecs import get_codec, CodecInterface
from speasy.core.cache import Cacheable, CACHE_ALLOWED_KWARGS  # _cache is used for tests (hack...)
from speasy.core.dataprovider import DataProvider, ParameterRangeCheck, GET_DATA_ALLOWED_KWARGS, register_provider
from speasy.core.http import is_server_up
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import ParameterIndex, DatasetIndex, SpeasyIndex, make_inventory_node
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
from speasy.core.requests_scheduling import SplitLargeRequests
from speasy.config import csa as csa_cfg
from speasy.core.url_utils import build_url
from speasy.products.variable import SpeasyVariable

log = logging.getLogger(__name__)


def _only_primitive_types(d: dict) -> dict:
    for k, v in d.items():
        if not isinstance(v, (int, bool, str, type(None), list, tuple, set)):
            if isinstance(v, np.integer):
                d[k] = int(v)
            elif isinstance(v, np.floating):
                d[k] = float(v)
            elif isinstance(v, (np.bool_,bool)):
                d[k] = bool(v)
            elif isinstance(v, np.str_):
                d[k] = str(v)
            elif isinstance(v, np.ma.core.MaskedConstant):
                d[k] = None
            else:
                log.debug(f"Warning: removing non primitive type {type(v)} for key {k}")
    return d


def to_dataset_and_variable(index_or_str: ParameterIndex or str) -> Tuple[str, str]:
    if type(index_or_str) is str:
        parts = index_or_str.split('/')
    elif isinstance(index_or_str, ParameterIndex):
        parts = index_or_str.product.split('/')
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")
    assert len(parts) == 2
    return parts[0], parts[1]


def _instruments_group(observatories, instruments, names: str):
    """A dataset made by several instruments goes under one node named after all of them, placed under their
    common observatory, or under MULTIPLE when they span several."""
    key = ", ".join(sorted(name.strip() for name in names.split(",")))
    if key not in instruments:
        homes = {getattr(instruments.get(name), 'observatories', 'MULTIPLE') for name in key.split(", ")}
        register_instrument(observatories, instruments,
                            {'name': key, 'observatories': homes.pop() if len(homes) == 1 else 'MULTIPLE'})
    return instruments[key]


def register_dataset(observatories, instruments, datasets, dataset):
    meta = dict(dataset)
    meta['stop_date'] = meta.pop('end_date')
    name = fix_name(meta['dataset_id'])
    parent = instruments.get(dataset['instruments']) or _instruments_group(observatories, instruments, dataset['instruments'])
    node = make_inventory_node(parent, DatasetIndex, name=name,
                               provider="csa",
                               uid=meta['dataset_id'], **_only_primitive_types(meta))
    datasets[meta['dataset_id']] = node


def register_observatory(missions, observatories, observatory):
    meta = dict(observatory)
    name = meta.pop('name')
    node = make_inventory_node(missions[observatory['mission_name']], SpeasyIndex,
                               name=fix_name(name),
                               provider="csa",
                               uid=name,
                               **_only_primitive_types(meta))
    observatories[name] = node


def register_mission(inventory_tree, missions, mission):
    meta = dict(mission)
    name = meta.pop('name')
    node = make_inventory_node(inventory_tree, SpeasyIndex, name=fix_name(name),
                               provider="csa",
                               uid=name, **_only_primitive_types(meta))
    missions[name] = node


def register_instrument(observatories, instruments, instrument):
    meta = dict(instrument)
    name = meta.pop('name')
    node = make_inventory_node(observatories.get(instrument['observatories'], observatories['MULTIPLE']),
                               SpeasyIndex, name=fix_name(name),
                               provider="csa",
                               uid=name, **_only_primitive_types(meta))
    instruments[name] = node


def register_param(datasets, parameter):
    parent_dataset = datasets.get(parameter["dataset_id"], None)
    if parent_dataset is not None:
        meta = dict(parameter)
        meta['dataset'] = parameter["dataset_id"]
        meta['start_date'] = parent_dataset.start_date
        meta['stop_date'] = parent_dataset.stop_date
        name = fix_name(meta['parameter_id'])
        make_inventory_node(parent_dataset, ParameterIndex, name=name,
                            provider="csa", uid=f"{parameter['dataset_id']}/{parameter['parameter_id']}",
                            **_only_primitive_types(meta))


def build_inventory(root: SpeasyIndex, tapurl="https://csa.esac.esa.int/csa-sl-tap/tap/"):
    missions_req = tap.query(tapurl, "SELECT * FROM csa.v_mission")
    observatories_req = tap.query(tapurl, "SELECT * FROM csa.v_observatory")
    instruments_req = tap.query(tapurl, "SELECT * FROM csa.v_instrument")
    datasets_req = tap.query(tapurl, "SELECT * FROM csa.v_dataset WHERE dataset_id like '%GRMB' OR is_cef='true'")
    parameters_req = tap.query(tapurl, "SELECT * FROM csa.v_parameter WHERE data_type='Data' AND value_type<>'CHAR'")
    missions = {}
    observatories = {}
    instruments = {}
    datasets = {}
    for mission in missions_req:
        register_mission(root, missions, mission)
    for observatory in observatories_req:
        register_observatory(missions, observatories, observatory)
    for instrument in instruments_req:
        register_instrument(observatories, instruments, instrument)
    for dataset in datasets_req:
        register_dataset(observatories, instruments, datasets, dataset)
    for parameter in parameters_req:
        register_param(datasets, parameter)

    return root


_CODECS = {"CEF": "application/x-cef", "CDF_ISTP": "application/x-cdf"}

# simplify: speasy skips older proxies for CSA, their speasy rejects output_format. Lower it once they're gone.
CSA_MIN_PROXY_VERSION = Version("0.27.0")


def delivery_format(dataset: DatasetIndex, requested: str) -> str:
    """CSA serves every dataset as CEF, and some of them as CDF_ISTP too."""
    requested = requested.upper()
    if requested not in _CODECS:
        raise ValueError(f"CSA can't deliver {requested}, choose one of {', '.join(_CODECS)}")
    # inventories built before the CEF codec carry no is_istp flag, and list only CDF_ISTP datasets
    return requested if requested == "CEF" or getattr(dataset, "is_istp", True) else "CEF"


def cache_entry_name(prefix: str, product: str, start_time: str, output_format: str, **kwargs) -> str:
    # CDF_ISTP keeps the entries cached before CEF support
    suffix = "" if output_format == "CDF_ISTP" else "-cef"
    return f"{prefix}/{product}{suffix}/{start_time}"


def _load_variable(archive: io.IOBase, variable: str, codec: CodecInterface) -> Optional[SpeasyVariable]:
    with tarfile.open(fileobj=archive) as tar:
        member = next((member for member in tar.getmembers() if member.isfile()), None)
        if member is None:
            return None
        return codec.load_variable(file=tar.extractfile(member).read(), variable=variable)


def _download_variable(url: str, dataset: str, variable: str, start_time: datetime, stop_time: datetime,
                       delivery_format: str, extra_http_headers: Optional[Dict[str, str]] = None) \
        -> Optional[SpeasyVariable]:
    # https://csa.esac.esa.int/csa-sl-tap/data?RETRIEVAL_TYPE=product&&DATASET_ID=C3_CP_PEA_LERL_DEFlux&START_DATE=2001-06-10T22:12:14Z&END_DATE=2001-06-11T06:12:14Z&DELIVERY_FORMAT=CDF_ISTP&DELIVERY_INTERVAL=all
    archive = any_files.any_loc_open(
        build_url(base=url, parameters={
            "RETRIEVAL_TYPE": "product",
            "DATASET_ID": dataset,
            "START_DATE": start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "END_DATE": stop_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "DELIVERY_FORMAT": delivery_format,
            "DELIVERY_INTERVAL": "all"
        }),
        headers=dict(extra_http_headers or {}))
    return _load_variable(archive, variable, get_codec(_CODECS[delivery_format]))


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, output_format: str, **kwargs):
    return {'path': f"csa/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}', 'output_format': output_format}


@register_provider
class CsaWebservice(DataProvider):
    NAME = 'csa'
    BASE_URL = "https://csa.esac.esa.int"

    @classmethod
    def request_options(cls, output_format: Optional[str] = None, **kwargs) -> dict:
        # only what the caller passed counts, the config default differs between machines (same rule as AMDA)
        return {} if output_format is None else {'output_format': output_format.upper()}

    def __init__(self):
        DataProvider.__init__(self)
        self.__url = f"{self.BASE_URL}/csa-sl-tap/data"

    @staticmethod
    def is_server_up():
        return is_server_up(url=CsaWebservice.BASE_URL)

    def _dataset_range(self, dataset: str or DatasetIndex) -> DateTimeRange:
        if type(dataset) is str:
            dataset = self.flat_inventory.datasets[dataset]
        return DateTimeRange(dataset.start_date, dataset.stop_date)

    def _dl_variable(self,
                     dataset: str, variable: str,
                     start_time: datetime, stop_time: datetime, output_format: str,
                     extra_http_headers: Dict[str, str] or None = None) -> Optional[SpeasyVariable]:
        ds_range = self._dataset_range(dataset)
        if not ds_range.intersect(DateTimeRange(start_time, stop_time)):
            log.warning(f"You are requesting {dataset}/{variable} outside of its definition range {ds_range}")
            return None
        return _download_variable(self.__url, dataset, variable, start_time, stop_time, output_format,
                                  extra_http_headers)

    @staticmethod
    def build_inventory(root: SpeasyIndex):
        return build_inventory(root)

    def parameter_range(self, parameter_id: str or ParameterIndex) -> Optional[DateTimeRange]:
        """Get product time range.

        Parameters
        ----------
        parameter_id: str or ParameterIndex
            parameter id

        Returns
        -------
        Optional[DateTimeRange]
            Data time range

        Examples
        --------

        >>> import speasy as spz
        >>> spz.csa.parameter_range("C3_CP_WBD_WAVEFORM_BM2/B__C3_CP_WBD_WAVEFORM_BM2")
        <DateTimeRange: ... -> ...>

        """
        return self._parameter_range(parameter_id)

    def dataset_range(self, dataset_id: str or DatasetIndex) -> Optional[DateTimeRange]:
        """Get product time range.

        Parameters
        ----------
        dataset_id: str or DatasetIndex
            parameter id

        Returns
        -------
        Optional[DateTimeRange]
            Data time range

        Examples
        --------

        >>> import speasy as spz
        >>> spz.csa.dataset_range("D2_CP_FGM_SPIN")
        <DateTimeRange: 2004-07-27T00:00:00+00:00 -> ...>

        """
        return self._dataset_range(dataset_id)

    def product_last_update(self, product: str or ParameterIndex):
        """Get date of last modification of dataset or parameter.

        Parameters
        ----------
        product: str or ParameterIndex
            product

        Returns
        -------
        str
            product last update date
        """
        dataset, _ = to_dataset_and_variable(product)
        return self.flat_inventory.datasets[dataset].date_last_update

    def get_data(self, product, start_time: datetime, stop_time: datetime, output_format: Optional[str] = None,
                 **kwargs) -> Optional[SpeasyVariable]:
        """output_format: CEF or CDF_ISTP, defaults to speasy.config.csa.output_format. Datasets CSA doesn't serve
        as CDF_ISTP are read as CEF."""
        dataset, _ = to_dataset_and_variable(product)
        output_format = delivery_format(self.flat_inventory.datasets[dataset], output_format or csa_cfg.output_format())
        return self._get_data(product, start_time, stop_time, output_format=output_format, **kwargs)

    @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS + ['output_format'])
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @Cacheable(prefix="csa", fragment_hours=lambda x: 12, version=product_last_update, entry_name=cache_entry_name)
    @SplitLargeRequests(threshold=lambda x: timedelta(days=7))
    @Proxyfiable(GetProduct, get_parameter_args, min_version=CSA_MIN_PROXY_VERSION)
    def _get_data(self, product, start_time: datetime, stop_time: datetime, output_format: str,
                  extra_http_headers: Dict[str, str] or None = None):
        dataset, variable = to_dataset_and_variable(product)
        return self._dl_variable(start_time=start_time, stop_time=stop_time, dataset=dataset, variable=variable,
                                 output_format=output_format, extra_http_headers=extra_http_headers)

    def get_variable(self, dataset: str, variable: str, start_time: datetime or str, stop_time: datetime or str,
                     **kwargs) -> \
            Optional[SpeasyVariable]:
        return self.get_data(f"{dataset}/{variable}", start_time, stop_time, **kwargs)
