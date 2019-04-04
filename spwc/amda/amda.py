from .rest import AmdaRest
from .soap import AmdaSoap
import xmltodict
from datetime import datetime
import pandas as pds
import requests
from typing import Optional
from ..common import listify
from ..cache import _cache
from ..common.datetime_range import DateTimeRange
from functools import partial


class AMDA:
    class ObsDataTreeParser:
        @staticmethod
        def node_to_dict(node, **kwargs):
            d = {key.replace('@', ''): value for key, value in node.items() if type(value) is str}
            d.update(kwargs)
            return d

        @staticmethod
        def enter_nodes(node, storage, **kwargs):
            for key, value in storage.items():
                if key in node:
                    for subnode in listify(node[key]):
                        name = subnode['@xml:id']
                        kwargs[key] = name
                        value[name] = AMDA.ObsDataTreeParser.node_to_dict(subnode, **kwargs)
                        AMDA.ObsDataTreeParser.enter_nodes(subnode, storage=storage, **kwargs)

        @staticmethod
        def extrac_all(tree, storage):
            AMDA.ObsDataTreeParser.enter_nodes(tree['dataRoot'], storage)

    def __init__(self, wsdl: str = 'AMDA/public/wsdl/Methods_AMDA.wsdl', server_url: str = "http://amda.irap.omp.eu"):
        self.METHODS = {
            "REST": AmdaRest(server_url=server_url),
            "SOAP": AmdaSoap(server_url=server_url, wsdl=wsdl)
        }
        self.parameter = {}
        self.mission = {}
        self.observatory = {}
        self.instrument = {}
        self.dataset = {}
        self.datasetGroup = {}
        self.component = {}
        self.dataCenter = {}
        if "AMDA/inventory" in _cache:
            self._unpack_inventory(_cache["AMDA/inventory"])

    def __del__(self):
        _cache["AMDA/inventory"] = self._pack_inventory()

    def _pack_inventory(self):
        return {
            'parameter': self.parameter,
            'observatory': self.observatory,
            'instrument': self.instrument,
            'dataset': self.dataset,
            'mission': self.mission,
            'datasetGroup': self.datasetGroup,
            'component': self.component,
            'dataCenter': self.dataCenter
        }

    def _unpack_inventory(self, inventory):
        self.__dict__.update(inventory)

    def update_inventory(self, method="SOAP"):
        tree = self.get_obs_data_tree()
        storage = self._pack_inventory()
        AMDA.ObsDataTreeParser.extrac_all(tree, storage)

    def get_token(self, method: str = "SOAP", **kwargs: dict) -> str:
        return self.METHODS[method.upper()].get_token

    def _dl_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                      method: str = "SOAP", **kwargs) -> Optional[pds.DataFrame]:

        start_time = start_time.isoformat()
        stop_time = stop_time.isoformat()
        url = self.METHODS[method.upper()].get_parameter(
            startTime=start_time, stopTime=stop_time, parameterID=parameter_id, **kwargs)
        if url is not None:
            return pds.read_csv(url, delim_whitespace=True, comment='#', parse_dates=True, infer_datetime_format=True,
                                index_col=0, header=None)
        return None

    def get_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                      method: str = "SOAP", **kwargs) -> Optional[pds.DataFrame]:
        result = None
        cache_product = f"amda/{parameter_id}"
        result = _cache.get_data(cache_product, DateTimeRange(start_time, stop_time),
                                 partial(self._dl_parameter, parameter_id=parameter_id, method=method))
        return result

    def get_obs_data_tree(self, method="SOAP") -> dict:
        datatree = xmltodict.parse(requests.get(
            self.METHODS[method.upper()].get_obs_data_tree()).text)
        return datatree

    def parameter_range(self, parameter_id):
        if not len(self.parameter):
            self.update_inventory()
        dataset_name = None
        if parameter_id in self.parameter:
            dataset_name = self.parameter[parameter_id]['dataset']
        if parameter_id in self.component:
            dataset_name = self.component[parameter_id]['dataset']
        if dataset_name in self.dataset:
            dataset = self.dataset[dataset_name]
            return DateTimeRange(
                datetime.strptime(dataset["dataStart"], '%Y-%m-%dT%H:%M:%SZ'),
                datetime.strptime(dataset["dataStop"], '%Y-%m-%dT%H:%M:%SZ')
            )
