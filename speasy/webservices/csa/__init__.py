import requests
from astroquery.utils.tap.core import TapPlus
from typing import Optional, Tuple
from datetime import datetime
from speasy.core.cache import Cacheable, CACHE_ALLOWED_KWARGS  # _cache is used for tests (hack...)
from speasy.products.variable import SpeasyVariable
from speasy.core import http, AllowedKwargs, fix_name
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
from speasy.core.cdf import load_variable
from ...inventories import flat_inventories
from speasy.core.inventory.indexes import ParameterIndex, DatasetIndex, SpeasyIndex, make_inventory_node
from speasy.core.dataprovider import DataProvider
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from speasy.core.datetime_range import DateTimeRange
import tarfile
import logging

log = logging.getLogger(__name__)


def to_dataset_and_variable(index_or_str: ParameterIndex or str) -> Tuple[str, str]:
    if type(index_or_str) is str:
        parts = index_or_str.split('/')
    elif type(index_or_str) is ParameterIndex:
        parts = index_or_str.product.split('/')
    else:
        raise TypeError(f"given parameter {index_or_str} of type {type(index_or_str)} is not a compatible index")
    assert len(parts) == 2
    return parts[0], parts[1]


def register_dataset(inventory_tree, dataset):
    meta = {cname: dataset[cname] for cname in dataset.colnames}
    name = fix_name(meta['dataset_id'])
    make_inventory_node(flat_inventories.csa.instruments[dataset['instruments']], DatasetIndex, name=name,
                        provider="csa",
                        uid=meta['dataset_id'], **meta)


def register_observatory(inventory_tree, observatory):
    meta = {cname: observatory[cname] for cname in observatory.colnames}
    name = meta.pop('name')
    node = make_inventory_node(flat_inventories.csa.missions[observatory['mission_name']], SpeasyIndex,
                               name=fix_name(name),
                               provider="csa",
                               uid=name,
                               **meta)
    flat_inventories.csa.observatories[name] = node


def register_mission(inventory_tree, mission):
    meta = {cname: mission[cname] for cname in mission.colnames}
    name = meta.pop('name')
    node = make_inventory_node(inventory_tree, SpeasyIndex, name=fix_name(name),
                               provider="csa",
                               uid=name, **meta)
    flat_inventories.csa.missions[name] = node


def register_instrument(inventory_tree, instrument):
    meta = {cname: instrument[cname] for cname in instrument.colnames}
    name = meta.pop('name')
    node = make_inventory_node(flat_inventories.csa.observatories.get(instrument['observatories'],
                                                                      flat_inventories.csa.observatories['MULTIPLE']),
                               SpeasyIndex, name=fix_name(name),
                               provider="csa",
                               uid=name, **meta)
    flat_inventories.csa.instruments[name] = node


def register_param(parameter):
    if parameter["dataset_id"] in flat_inventories.csa.datasets:
        meta = {cname: parameter[cname] for cname in parameter.colnames}
        name = fix_name(meta['parameter_id'])
        make_inventory_node(flat_inventories.csa.datasets[parameter["dataset_id"]], ParameterIndex, name=name,
                            provider="csa", uid=f"{parameter['dataset_id']}/{parameter['parameter_id']}", **meta)


def build_inventory(root: SpeasyIndex, tapurl="https://csa.esac.esa.int/csa-sl-tap/tap/"):
    CSA = TapPlus(url=tapurl)
    missions_req = CSA.launch_job_async("SELECT * FROM csa.v_mission")
    observatories_req = CSA.launch_job_async("SELECT * FROM csa.v_observatory")
    instruments_req = CSA.launch_job_async("SELECT * FROM csa.v_instrument")
    datasets_req = CSA.launch_job_async("SELECT * FROM csa.v_dataset WHERE is_cef='true' AND is_istp='true'")
    parameters_req = CSA.launch_job_async("SELECT * FROM csa.v_parameter WHERE data_type='Data'")

    list(map(lambda m: register_mission(root, m), missions_req.get_results()))
    list(map(lambda o: register_observatory(root, o), observatories_req.get_results()))
    list(map(lambda i: register_instrument(root, i), instruments_req.get_results()))
    list(map(lambda d: register_dataset(root, d), datasets_req.get_results()))
    list(map(lambda p: register_param(p), parameters_req.get_results()))

    return root


def _read_cdf(req: requests.Response, variable: str) -> SpeasyVariable:
    with NamedTemporaryFile('wb') as tmp_tar:
        tmp_tar.write(req.content)
        tmp_tar.flush()
        with tarfile.open(tmp_tar.name) as tar:
            tarname = tar.getnames()
            if len(tarname):
                with TemporaryDirectory() as tmp_dir:
                    tar.extractall(tmp_dir)
                    return load_variable(file=f"{tmp_dir}/{tarname[0]}", variable=variable)


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"csa/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}


class CSA_Webservice(DataProvider):
    def __init__(self):
        DataProvider.__init__(self, provider_name='csa')
        self.__url = "https://csa.esac.esa.int/csa-sl-tap/data"

    def _dataset_range(self, dataset: str or DatasetIndex) -> DateTimeRange:
        if type(dataset) is str:
            dataset = self.flat_inventory.datasets[dataset]
        return DateTimeRange(dataset.start_date, dataset.end_date)

    def _dl_variable(self,
                     dataset: str, variable: str,
                     start_time: datetime, stop_time: datetime) -> Optional[SpeasyVariable]:

        # https://csa.esac.esa.int/csa-sl-tap/data?RETRIEVAL_TYPE=product&&DATASET_ID=C3_CP_PEA_LERL_DEFlux&START_DATE=2001-06-10T22:12:14Z&END_DATE=2001-06-11T06:12:14Z&DELIVERY_FORMAT=CDF_ISTP&DELIVERY_INTERVAL=all
        ds_range = self._dataset_range(dataset)
        if not ds_range.intersect(DateTimeRange(start_time, stop_time)):
            log.warning(f"You are requesting {dataset}/{variable} outside of its definition range {ds_range}")
            return None
        resp = http.get(self.__url, params={
            "RETRIEVAL_TYPE": "product",
            "DATASET_ID": dataset,
            "START_DATE": start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "END_DATE": stop_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "DELIVERY_FORMAT": "CDF_ISTP",
            "DELIVERY_INTERVAL": "all"
        })
        log.debug(f"{resp.url}")
        if resp.status_code != 200:
            raise RuntimeError(f'Failed to get data with request: {resp.url}, got {resp.status_code} HTTP response')
        if not resp.ok:
            return None
        return _read_cdf(resp, variable)

    @staticmethod
    def build_inventory(root: SpeasyIndex):
        return build_inventory(root)

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
        dataset, variable = to_dataset_and_variable(product)
        return self.flat_inventory.datasets[dataset].date_last_update

    @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + ['product', 'start_time', 'stop_time'])
    @Cacheable(prefix="csa", fragment_hours=lambda x: 12, version=product_last_update)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_data(self, product, start_time: datetime, stop_time: datetime):
        dataset, variable = to_dataset_and_variable(product)
        return self._dl_variable(start_time=start_time, stop_time=stop_time, dataset=dataset,
                                 variable=variable)

    def get_variable(self, dataset: str, variable: str, start_time: datetime or str, stop_time: datetime or str,
                     **kwargs) -> \
        Optional[SpeasyVariable]:
        return self.get_data(f"{dataset}/{variable}", start_time, stop_time, **kwargs)
