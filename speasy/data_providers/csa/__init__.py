import io
import logging
import tarfile
from datetime import datetime, timedelta
from tempfile import TemporaryDirectory
from typing import Optional, Tuple, Dict

import numpy as np
from astroquery.utils.tap.core import TapPlus

from speasy.core import any_files, AllowedKwargs, fix_name, EnsureUTCDateTime
from speasy.core.codecs import get_codec, CodecInterface
from speasy.core.cache import Cacheable, CACHE_ALLOWED_KWARGS  # _cache is used for tests (hack...)
from speasy.core.dataprovider import DataProvider, ParameterRangeCheck, GET_DATA_ALLOWED_KWARGS
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import ParameterIndex, DatasetIndex, SpeasyIndex, make_inventory_node
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
from speasy.core.requests_scheduling import SplitLargeRequests
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


def register_dataset(instruments, datasets, dataset):
    meta = {cname: dataset[cname] for cname in dataset.colnames}
    meta['stop_date'] = meta.pop('end_date')
    name = fix_name(meta['dataset_id'])
    node = make_inventory_node(instruments[dataset['instruments']], DatasetIndex, name=name,
                               provider="csa",
                               uid=meta['dataset_id'], **_only_primitive_types(meta))
    datasets[meta['dataset_id']] = node


def register_observatory(missions, observatories, observatory):
    meta = {cname: observatory[cname] for cname in observatory.colnames}
    name = meta.pop('name')
    node = make_inventory_node(missions[observatory['mission_name']], SpeasyIndex,
                               name=fix_name(name),
                               provider="csa",
                               uid=name,
                               **_only_primitive_types(meta))
    observatories[name] = node


def register_mission(inventory_tree, missions, mission):
    meta = {cname: mission[cname] for cname in mission.colnames}
    name = meta.pop('name')
    node = make_inventory_node(inventory_tree, SpeasyIndex, name=fix_name(name),
                               provider="csa",
                               uid=name, **_only_primitive_types(meta))
    missions[name] = node


def register_instrument(observatories, instruments, instrument):
    meta = {cname: instrument[cname] for cname in instrument.colnames}
    name = meta.pop('name')
    node = make_inventory_node(observatories.get(instrument['observatories'], observatories['MULTIPLE']),
                               SpeasyIndex, name=fix_name(name),
                               provider="csa",
                               uid=name, **_only_primitive_types(meta))
    instruments[name] = node


def register_param(datasets, parameter):
    parent_dataset = datasets.get(parameter["dataset_id"], None)
    if parent_dataset is not None:
        meta = {cname: parameter[cname] for cname in parameter.colnames}
        meta['dataset'] = parameter["dataset_id"]
        meta['start_date'] = parent_dataset.start_date
        meta['stop_date'] = parent_dataset.stop_date
        name = fix_name(meta['parameter_id'])
        make_inventory_node(parent_dataset, ParameterIndex, name=name,
                            provider="csa", uid=f"{parameter['dataset_id']}/{parameter['parameter_id']}",
                            **_only_primitive_types(meta))


def build_inventory(root: SpeasyIndex, tapurl="https://csa.esac.esa.int/csa-sl-tap/tap/"):
    CSA = TapPlus(url=tapurl)
    missions_req = CSA.launch_job_async("SELECT * FROM csa.v_mission")
    observatories_req = CSA.launch_job_async("SELECT * FROM csa.v_observatory")
    instruments_req = CSA.launch_job_async("SELECT * FROM csa.v_instrument")
    datasets_req = CSA.launch_job_async(
        "SELECT * FROM csa.v_dataset WHERE  dataset_id like '%GRMB' OR (is_cef='true' AND is_istp='true')")
    parameters_req = CSA.launch_job_async("SELECT * FROM csa.v_parameter WHERE data_type='Data' AND value_type<>'CHAR'")
    missions = {}
    observatories = {}
    instruments = {}
    datasets = {}
    list(map(lambda m: register_mission(root, missions, m), missions_req.get_results()))
    list(map(lambda o: register_observatory(missions, observatories, o), observatories_req.get_results()))
    list(map(lambda i: register_instrument(observatories, instruments, i), instruments_req.get_results()))
    list(map(lambda d: register_dataset(instruments, datasets, d), datasets_req.get_results()))
    list(map(lambda p: register_param(datasets, p), parameters_req.get_results()))

    return root


def _load_variable(archive: io.BytesIO, variable: str, cdf_codec: CodecInterface) -> Optional[SpeasyVariable]:
    with tarfile.open(fileobj=archive) as tar:
        tarname = tar.getnames()
        if len(tarname):
            with TemporaryDirectory() as tmp_dir:
                tar.extractall(tmp_dir)
                return cdf_codec.load_variable(file=f"{tmp_dir}/{tarname[0]}", variable=variable)
    return None


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"csa/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}


class CsaWebservice(DataProvider):
    BASE_URL = "https://csa.esac.esa.int"

    def __init__(self):
        DataProvider.__init__(self, provider_name='csa')
        self.__url = f"{self.BASE_URL}/csa-sl-tap/data"
        self._cdf_codec = get_codec("application/x-cdf")

    def _dataset_range(self, dataset: str or DatasetIndex) -> DateTimeRange:
        if type(dataset) is str:
            dataset = self.flat_inventory.datasets[dataset]
        return DateTimeRange(dataset.start_date, dataset.stop_date)

    def _dl_variable(self,
                     dataset: str, variable: str,
                     start_time: datetime, stop_time: datetime, extra_http_headers: Dict[str, str] or None = None) -> \
            Optional[SpeasyVariable]:

        # https://csa.esac.esa.int/csa-sl-tap/data?RETRIEVAL_TYPE=product&&DATASET_ID=C3_CP_PEA_LERL_DEFlux&START_DATE=2001-06-10T22:12:14Z&END_DATE=2001-06-11T06:12:14Z&DELIVERY_FORMAT=CDF_ISTP&DELIVERY_INTERVAL=all
        ds_range = self._dataset_range(dataset)
        if not ds_range.intersect(DateTimeRange(start_time, stop_time)):
            log.warning(f"You are requesting {dataset}/{variable} outside of its definition range {ds_range}")
            return None
        headers = {}
        if extra_http_headers is not None:
            headers.update(extra_http_headers)
        return _load_variable(
            any_files.any_loc_open(
                build_url(base=self.__url, parameters={
                    "RETRIEVAL_TYPE": "product",
                    "DATASET_ID": dataset,
                    "START_DATE": start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    "END_DATE": stop_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    "DELIVERY_FORMAT": "CDF_ISTP",
                    "DELIVERY_INTERVAL": "all"
                }),
                headers=headers),
            variable, cdf_codec=self._cdf_codec)

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

    @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS)
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @Cacheable(prefix="csa", fragment_hours=lambda x: 12, version=product_last_update)
    @SplitLargeRequests(threshold=lambda x: timedelta(days=7))
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_data(self, product, start_time: datetime, stop_time: datetime,
                 extra_http_headers: Dict[str, str] or None = None):
        dataset, variable = to_dataset_and_variable(product)
        return self._dl_variable(start_time=start_time, stop_time=stop_time, dataset=dataset,
                                 variable=variable, extra_http_headers=extra_http_headers)

    def get_variable(self, dataset: str, variable: str, start_time: datetime or str, stop_time: datetime or str,
                     **kwargs) -> \
            Optional[SpeasyVariable]:
        return self.get_data(f"{dataset}/{variable}", start_time, stop_time, **kwargs)
