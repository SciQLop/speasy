from .rest import AmdaRest
from .soap import AmdaSoap
import xmltodict
from datetime import datetime, timezone
import pandas as pds
import numpy as np
import requests
from typing import Optional
from ..common import listify
from ..cache import _cache, Cacheable
from ..common.datetime_range import DateTimeRange
from ..common.variable import SpeasyVariable
from ..proxy import Proxyfiable, GetProduct
from urllib.request import urlopen
import os
import logging
from enum import Enum
from lxml import etree

log = logging.getLogger(__name__)


def load_csv(filename: str):
    """Load a CSV file

    :param filename: CSV filename
    :type filename: str
    :return: CSV contents
    :rtype: SpeasyVariable
    """
    if '://' not in filename:
        filename = f"file://{os.path.abspath(filename)}"
    with urlopen(filename) as csv:
        line = csv.readline().decode()
        meta = {}
        y = None
        while line[0] == '#':
            if ':' in line:
                key, value = line[1:].split(':', 1)
                meta[key.strip()] = value.strip()
            line = csv.readline().decode()
        columns = [col.strip() for col in meta['DATA_COLUMNS'].split(',')[:]]
        with urlopen(filename) as f:
            data = pds.read_csv(f, comment='#', delim_whitespace=True, header=None, names=columns).values.transpose()
        time, data = data[0], data[1:].transpose()
        if "PARAMETER_TABLE_MIN_VALUES[1]" in meta:
            min_v = np.array([float(v) for v in meta["PARAMETER_TABLE_MIN_VALUES[1]"].split(',')])
            max_v = np.array([float(v) for v in meta["PARAMETER_TABLE_MAX_VALUES[1]"].split(',')])
            y = (max_v + min_v) / 2.
        elif "PARAMETER_TABLE_MIN_VALUES[0]" in meta:
            min_v = np.array([float(v) for v in meta["PARAMETER_TABLE_MIN_VALUES[0]"].split(',')])
            max_v = np.array([float(v) for v in meta["PARAMETER_TABLE_MAX_VALUES[0]"].split(',')])
            y = (max_v + min_v) / 2.
        return SpeasyVariable(time=time, data=data, meta=meta, columns=columns[1:], y=y)
def load_timetable(filename: str):
    """Load a timetable file

    :param filename: filename
    :type filename: str
    :return: TimeTable
    :rtype: ????

    """
    if '://' not in filename:
        filename = f"file://{os.path.abspath(filename)}"
    with urlopen(filename) as votable:
        parser=etree.XMLParser(recover=True)
        return etree.parse(votable, parser=parser)



def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    """Get parameter arguments

    :param start_time: parameter start time
    :type start_time: datetime.datetime
    :param stop_time: parameter stop time
    :type stop_time: datetime.datetime
    :return: parameter arguments in dictionary
    :rtype: dict
    """
    return {'path': f"amda/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}

class AMDAProduct(Enum):
    """Enumeration of the type of products available in AMDA.
    """
    UNKNOWN=0
    DATASET=1
    PARAMETER=2
    COMPONENT=3
    TIMETABLE=4
    CATALOG=5


class AMDA:
    """AMDA connexion class. This class manages the connexion to AMDA. Use the :meth:`get_data` or
    :meth:`get_parameter` methods for retrieving data.
    """
    class ObsDataTreeParser:
        """Class for storing the observatory data tree structure providing a listing of available
        products in AMDA
        """
        @staticmethod
        def node_to_dict(node, **kwargs):
            """Convert node of the observatory tree to dictionary

            :param node: tree node
            :type node: ??
            :return: node as dictionary
            :rtype: dict
            """
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
        pass

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
        _cache.set("AMDA/inventory", self._pack_inventory(), expire=7 * 24 * 60 * 60)

    def get_token(self, **kwargs: dict) -> str:
        return self.METHODS["REST"].get_token

    def _dl_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                      method: str = "REST", **kwargs) -> Optional[SpeasyVariable]:

        start_time = start_time.timestamp()
        stop_time = stop_time.timestamp()
        url = self.METHODS[method.upper()].get_parameter(
            startTime=start_time, stopTime=stop_time, parameterID=parameter_id, timeFormat='UNIXTIME', **kwargs)
        if url is not None:
            var = load_csv(url)
            if len(var):
                log.debug(
                    'Loaded var: data shape = {shape}, data start time = {start_time}, data stop time = {stop_time}'.format(
                        shape=var.values.shape,
                        start_time=datetime.utcfromtimestamp(var.time[0]),
                        stop_time=datetime.utcfromtimestamp(var.time[-1])))
            else:
                log.debug('Loaded var: Empty var')
            return var
        return None
    def _dl_timetable(self, timetable_id: str, method: str = "REST", **kwargs):
        url = self.METHODS[method.upper()].get_timetable(ttID=timetable_id)
        if not url is None:
            var = load_timetable(url)
            if var:
                log.debug(
                    'Loaded tt: id = {}'.format(timetable_id))
            else:
                log.debug('Loaded tt: Empty tt')
            return var
        return None


    def product_version(self, parameter_id):
        return self.dataset[self.parameter[parameter_id]["dataset"]]['lastUpdate']

    @Cacheable(prefix="amda", version=product_version, fragment_hours=lambda x: 12)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_data(self, product, start_time: datetime, stop_time: datetime):
        """Get product data

        :param product: product id
        :type product: str
        :param start_time: desired data start time
        :type start_time: datetime.datetime
        :param stop_time: desired data stop time
        :type stop_time: datetime.datetime
        :return: product data if available
        :rtype: SpeasyVariable

        Example::

            >>> imf_data = amda.get_data("imf", datetime.datetime(2000,1,1), datetime.datetime(2000,2,1))
        """
        log.debug(
            'Get data: product = {product}, data start time = {start_time}, data stop time = {stop_time}'.format(
                product=product, start_time=start_time, stop_time=stop_time))
        return self._dl_parameter(start_time=start_time, stop_time=stop_time, parameter_id=product)

    def get_parameter(self,  parameter_id: str, start_time: datetime, stop_time: datetime,
                      method: str = "REST", **kwargs) -> Optional[SpeasyVariable]:
        """Get parameter data

        :param parameter_id: parameter id
        :type parameter_id: str
        :param start_time: desired data start time
        :type start_time: datetime.datetime
        :param stop_time: desired data stop time
        :type stop_time: datetime.datetime
        :param method: retrieval method (default: REST)
        :type method: str
        :param kwargs: optional arguments
        :type kwargs: dict
        :return: product data if available
        :rtype: SpeasyVariable

        Example::

            >>> imf_data = amda.get_parameter("imf", datetime.datetime(2000,1,1), datetime.datetime(2000,2,1))

        """


        return self.get_data(product=parameter_id, start_time=start_time, stop_time=stop_time, **kwargs)
    
    def get_dataset(self, dataset_id: str, start: datetime, stop: datetime):
        """Get dataset contents. TEMPORARY : returns list of SpeasyVariable objects, one for each
        parameter in the dataset

        :param dataset_id: dataset id
        :type dataset_id: str
        :param start: desired data start
        :type start: datetime
        :param stop: desired data end
        :type stop: datetime
        :return: dataset content
        :rtype: list[SpeasyVariable]

        Example::

            >>> dataset = amda.get_dataset("ace-imf-all", datetime.datetime(2000,1,1), datetime.datetime(2000,2,1))
            >>> dataset
            [<speasy.common.variable.SpeasyVariable object at 0x7f01f17487c0>, <speasy.common.variable.SpeasyVariable object at 0x7f01f174f5e0>, <speasy.common.variable.SpeasyVariable object at 0x7f01f16ad090>]

        """
        # get list of parameters for this dataset
        parameters = self.list_parameters(dataset_id)
        return [self.get_parameter(p, start, stop) for p in parameters]

    def get_timetable(self, timetable_id: str):
        """Get timetable data (NOT YET IMPLEMENTED)

        :param timetable_id: time table id
        :type timetable_id: str
        :return: timetable data
        :rtype: ???
        """
        return self._dl_timetable(timetable_id)

    def get_catalog(self, catalog_id: str):
        """Get catalog data (NOT YET IMPLEMENTED)

        :param catalog_id: catalog id
        :type catalog_id: str
        :return: catalog data
        :rtype: ???
        """
        pass


    def get_obs_data_tree(self, method="SOAP") -> dict:
        datatree = xmltodict.parse(requests.get(
            self.METHODS[method.upper()].get_obs_data_tree()).text)
        return datatree

    def parameter_range(self, parameter_id):
        """Get product time range.

        :param parameter_id: product id
        :type parameter_id: str
        :return: Data time range
        :rtype: DateTimeRange
        """
        if not len(self.parameter):
            self.update_inventory()
        dataset_name = None

        # added support for dataset time range
        product_type=self.get_product_type(parameter_id)
        if product_type==AMDAProduct.PARAMETER:
            dataset_name = self.parameter[parameter_id]["dataset"]
        elif product_type==AMDAProduct.DATASET:
            dataset_name = parameter_id
        elif product_type==AMDAProduct.COMPONENT:
            dataset_name = self.component[parameter_id]["dataset"]
        else:
            return


        if dataset_name in self.dataset:
            dataset = self.dataset[dataset_name]
            return DateTimeRange(
                datetime.strptime(dataset["dataStart"], '%Y-%m-%dT%H:%M:%SZ'),
                datetime.strptime(dataset["dataStop"], '%Y-%m-%dT%H:%M:%SZ')
            )
    def list_parameters(self, dataset_id=None):
        """Get list of parameter id available in AMDA

        :param dataset_id: optional parent dataset id
        :type dataset_id: str
        :return: list of parameter ids
        :rtype: list[str]
        """
        if not dataset_id is None:
            return [k for k in self.parameter if self.parameter[k]["dataset"]==dataset_id]
        return [k for k in self.parameter]
    def list_datasets(self):
        """Get list of dataset id available in AMDA

        :return: list if dataset ids
        :rtype: list[str]
        """
        return [k for k in self.dataset]
    def get_product_type(self, product_id):
        """Get product type.

        :param product_id: product id
        :type product_id: str
        :return: Type of product
        :rtype: AMDAProduct
        """
        if product_id in self.dataset:
            return AMDAProduct.DATASET
        if product_id in self.parameter:
            return AMDAProduct.PARAMETER
        if product_id in self.component:
            return AMDAProduct.COMPONENT
        return AMDAProduct.UNKNOWN

