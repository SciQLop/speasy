from .rest import AmdaRest
from .soap import AmdaSoap
import xmltodict
from datetime import datetime, timezone
import pandas as pds
import requests
from typing import Optional
from ..common import listify, make_utc_datetime
from ..cache import _cache
from ..common.datetime_range import DateTimeRange
from ..common.variable import SpwcVariable
from functools import partial
from urllib.request import urlopen
import os


def load_csv(filename: str):
    if '://' not in filename:
        filename = f"file://{os.path.abspath(filename)}"
    with urlopen(filename) as csv:
        line = csv.readline().decode()
        meta = {}
        columns = []
        while line[0] == '#':
            if ':' in line:
                key, value = line[1:].split(':', 1)
                meta[key.strip()] = value.strip()
            line = csv.readline().decode()
        data = pds.read_csv(csv, comment='#', delim_whitespace=True).values.transpose()
        time, data = data[0], data[1:].transpose()
        if 'DATA_COLUMNS' in meta:
            columns = [col.strip() for col in meta['DATA_COLUMNS'].split(',')[1:]]
        return SpwcVariable(time=time, data=data, meta=meta, columns=columns)


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
        else:
            self.update_inventory()

    def __del__(self):
        _cache.set("AMDA/inventory", self._pack_inventory(), expire=7 * 24 * 60 * 60)

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

    def get_token(self, **kwargs: dict) -> str:
        return self.METHODS["REST"].get_token

    def _dl_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                      method: str = "SOAP", **kwargs) -> Optional[SpwcVariable]:

        start_time = start_time.timestamp()
        stop_time = stop_time.timestamp()
        url = self.METHODS[method.upper()].get_parameter(
            startTime=start_time, stopTime=stop_time, parameterID=parameter_id, timeFormat='UNIXTIME', **kwargs)
        if url is not None:
            var = load_csv(url)
            return var
        return None

    def get_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                      method: str = "SOAP", **kwargs) -> Optional[SpwcVariable]:
        cache_product = f"amda/{parameter_id}"
        start_time = make_utc_datetime(start_time)
        stop_time = make_utc_datetime(stop_time)
        version = self.dataset[self.parameter[parameter_id]["dataset"]]['lastUpdate']
        result = _cache.get_data(cache_product, DateTimeRange(start_time, stop_time),
                                 partial(self._dl_parameter, parameter_id=parameter_id, method=method),
                                 fragment_hours=12, version=version)
        return result

    def get_data(self, path, start_time: datetime, stop_time: datetime):
        return self.get_parameter(start_time=start_time, stop_time=stop_time, parameter_id=path)

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
