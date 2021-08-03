"""
speasy.amda.amda
----------------

This module contains the definition of the :class:`~speasy.amda.amda.AMDA` class, the object that
manages the connexion to AMDA and allows users to list available products, get informations about
that product and downloading the corresponding data.

AMDA provides the following products : 
    - parameters (:meth:`~speasy.amda.amda.AMDA.get_parameter()`) : time-series 
    - datasets (:meth:`~speasy.amda.amda.AMDA.get_dataset()`) : collection of parameters with same time base
    - timetables (:meth:`~speasy.amda.amda.AMDA.get_timetable()`) 
    - catalogs (:meth:`~speasy.amda.amda.AMDA.get_catalog()`)

Every product has a unique identifier, users can use the :meth:`~speasy.amda.amda.AMDA.list_parameters()` and :meth:`~speasy.amda.amda.AMDA.list_datasets()` methods to retrieve the list of available datasets
and parameters. 


"""

# AMDA, provider specific modules
from .rest import AmdaRest
from .soap import AmdaSoap
from .obstree import ObsDataTreeParser
from .tttree import TimeTableTree
from .utils import load_csv, load_timetable, get_parameter_args, load_catalog

import io
import xmltodict
from datetime import datetime, timezone
import pandas as pds
import numpy as np
import requests
from typing import Optional

# General modules
from ..config import ConfigEntry
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


class ProductType(Enum):
    """Enumeration of the type of products available in AMDA.
    """
    UNKNOWN=0
    DATASET=1
    PARAMETER=2
    COMPONENT=3
    TIMETABLE=4
    CATALOG=5


class AMDA:
    __datetime_format__="%Y-%m-%dT%H:%M:%S.%f"
    """AMDA connexion class. This class manages the connexion to AMDA. Use the :meth:`get_data` or
    :meth:`get_parameter` methods for retrieving data.

    Initialize the connexion::

        >>> from speasy.amda import AMDA
        >>> amda = AMDA()

    """
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
        self.folder = {}
        self.timeTable = {}
        self.catalog = {}
        if "AMDA/inventory" in _cache:
            self._unpack_inventory(_cache["AMDA/inventory"])
        else:
            self.update_inventory()
    @property
    def timetable(self):
        return self.timeTable
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
            'dataCenter': self.dataCenter,
            'folder': self.folder,
            'timeTable': self.timeTable,
            'catalog': self.catalog
        }

    def _unpack_inventory(self, inventory):
        self.__dict__.update(inventory)

    def update_inventory(self, method="SOAP"):
        """Load AMDA invertory and save to cache.

        :param method: update method (default: SOAP)
        :type method: str
        """
        tree = self.get_obs_data_tree()
        storage = self._pack_inventory()
        ObsDataTreeParser.extrac_all(tree, storage)
        from .inventory import InventoryTree
        # get timetable inventory
        tttree=self.get_timetable_tree()
        InventoryTree.extrac_all(tttree["timeTableList"], storage)
        # get catalog inventory
        cattree=self.get_catalog_tree()
        InventoryTree.extrac_all(cattree["catalogList"], storage)
        #_cache.set("AMDA/inventory", self._pack_inventory(), expire=7 * 24 * 60 * 60)
        _cache.set("AMDA/inventory", storage, expire=7 * 24 * 60 * 60)

    def get_token(self, **kwargs: dict) -> str:
        """Get authentication token.

        :param kwargs: keyword arguments
        :type kwargs: dict
        :return: authentication token
        :rtype: str
        """
        return self.METHODS["REST"].get_token
    def _dl_user_parameter(self, parameter_id: str, username: str, password: str, start_time: datetime, stop_time: datetime):
        url=self.METHODS["REST"].get_parameter(parameterID=parameter_id,userID=username, password=password, startTime=start_time.strftime(self.__datetime_format__), stopTime=stop_time.strftime(self.__datetime_format__))

        if not url is None:
            var=load_csv(url)
            if len(var):
                log.debug("Loaded user parameter : data shape {shape}, username {username}".format(
                    shape=var.values.shape, username=username))
            else:
                log.debug("Loaded user parameter : empty var")
            return var
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
                    'Loaded timetable: id = {}'.format(timetable_id))
            else:
                log.debug('Loaded timetable: Empty tt')
            return var
        return None
    def _dl_catalog(self, catalog_id: str, method: str = "REST", **kwargs):
        url = self.METHODS[method.upper()].get_catalog(catID=catalog_id)
        if not url is None:
            var = load_catalog(url)
            if var:
                log.debug(
                    'Loaded catalog: id = {}'.format(catalog_id))
            else:
                log.debug('Loaded catalog: Empty catalog')
            return var
        return None



    def product_version(self, parameter_id):
        """Get date of last modification of dataset or parameter.

        :param parameter_id: parameter id
        :type parameter_id: str
        :return: product version
        :rtype: str
        """
        return self.dataset[self.parameter[parameter_id]["dataset"]]['lastUpdate']

    @Cacheable(prefix="amda", version=product_version, fragment_hours=lambda x: 12)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_data(self, product, start_time: datetime, stop_time: datetime):
        """Get product data by id. 

        :param product: product id
        :type product: str
        :param start_time: desired data start time
        :type start_time: datetime.datetime
        :param stop_time: desired data stop time
        :type stop_time: datetime.datetime
        :return: product data if available
        :rtype: SpeasyVariable

        Example::

            >>> imf_data = speasy.amda.AMDA().get_data("imf", start, stop)
            >>> # same as
            >>> imf_data = speasy.get_data("amda/imf", start, stop)

        """
        log.debug(
            'Get data: product = {product}, data start time = {start_time}, data stop time = {stop_time}'.format(
                product=product, start_time=start_time, stop_time=stop_time))
        return self._dl_parameter(start_time=start_time, stop_time=stop_time, parameter_id=product)
    def get_user_parameter(self, parameter_id: str, start_time: datetime, stop_time: datetime):
        """Get user parameter. Raises an exception if user is not authenticated.


        :param parameter_id: parameter id
        :type parameter_id: str
        :param start_time: begining of data time
        :type start_time: datetime.datetime
        :param stop_time: end of data time
        :type stop_time: datetime.datetime
        :return: user parameter
        :rtype: speasy.common.variable.SpeasyVariable

        Example::

           >>> amda.get_user_parameter("ws_0")
           <speasy.common.variable.SpeasyVariable object at 0x7f078a0eb6d0>

        .. warning::
            Calling :meth:`~speasy.amda.amda.AMDA.get_user_parameter` without having defined AMDA
            login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
            exception being raised.

        """
        username=ConfigEntry("AMDA","username").get()
        password=ConfigEntry("AMDA","password").get()
        return self._dl_user_parameter(parameter_id=parameter_id, username=username, password=password, start_time=start_time, stop_time=stop_time)

    def get_parameter(self,  parameter_id: str, start_time: datetime, stop_time: datetime,
                      method: str = "REST", **kwargs) -> Optional[SpeasyVariable]:
        """Get parameter data.

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
    
    def get_dataset(self, dataset_id: str, start: datetime, stop: datetime, **kwargs):
        """Get dataset contents. Returns list of SpeasyVariable objects, one for each
        parameter in the dataset.

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
        return [self.get_parameter(p, start, stop, **kwargs) for p in parameters]

    def get_timetable(self, timetable_id: str):
        """Get timetable data by ID.

        :param timetable_id: time table id
        :type timetable_id: str
        :return: timetable data
        :rtype: speasy.common.variable.SpeasyVariable

        Example::

           >>> amda.get_timetable("sharedtimeTable_0")
           <speasy.common.variable.SpeasyVariable object at 0x7efce01b3f90>

        """
        return self._dl_timetable(timetable_id)

    def get_catalog(self, catalog_id: str):
        """Get catalog data by ID.

        :param catalog_id: catalog id
        :type catalog_id: str
        :return: catalog data
        :rtype: speasy.common.variable.SpeasyVariable

        Example::

           >>> amda.get_catalog("sharedcatalog_0")
           <speasy.common.variable.SpeasyVariable object at 0x7f829cc644a0>

        """
        return self._dl_catalog(catalog_id)


    def get_obs_data_tree(self, method="SOAP") -> dict:
        """Get observatory data tree, a XML file containing information about available products.
        
        :param method: retrieval method (default: SOAP)
        :type method: str
        :return: observatory data tree
        :rtype: dict
        """
        ttt=requests.get(
            self.METHODS[method.upper()].get_obs_data_tree()).text
        datatree = xmltodict.parse(ttt)
        return datatree
    def get_timetable_tree(self, method="REST"):
        """Get timetable tree, XML file containing information about all timetables in AMDA.

        :param method: retrieval method (default: REST)
        :type method: str
        :return: timetable inventory tree
        :rtype: dict
        """
        ttt=self.METHODS[method.upper()].get_timetable_list()
        content= xmltodict.parse(ttt)
        return content
    def get_catalog_tree(self, method="REST"):
        """Get catalog tree, XML file containing information about public catalogs in AMDA.

        :param method: retrieval method (default: REST)
        :type method: str
        :return: catalog inventory tree
        :rtype: dict
        """
        ttt=self.METHODS[method.upper()].get_catalog_list()
        content= xmltodict.parse(ttt)
        return content


    def parameter_range(self, parameter_id):
        """Get product time range.

        :param parameter_id: product id
        :type parameter_id: str
        :return: Data time range
        :rtype: DateTimeRange

        Example::

           >>> amda.parameter_range("imf")
           1997-09-02T00:00:12->2021-07-24T23:59:53

        """
        if not len(self.parameter):
            self.update_inventory()
        dataset_name = None

        # added support for dataset time range
        product_type=self.get_product_type(parameter_id)
        if product_type==ProductType.PARAMETER:
            dataset_name = self.parameter[parameter_id]["dataset"]
        elif product_type==ProductType.DATASET:
            dataset_name = parameter_id
        elif product_type==ProductType.COMPONENT:
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

        Example::

           >>> for parameter_id in amda.list_parameters():
           >>>     print(parameter_id)
           imf_mag
           ...
           wnd_swe_pdyn

        """
        if not dataset_id is None:
            return [k for k in self.parameter if self.parameter[k]["dataset"]==dataset_id]
        return [k for k in self.parameter]
    def list_catalogs(self):
        """Get list of public catalog IDs:

        :return: list of catalog IDs
        :rtype: list[str]

        Example::

            >>> for catalog_id in amda.list_catalogs():
            >>>     print(catalog_id)
            sharedcatalog_0
            ...
            sharedcatalog_16

        """
        return [k for k in self.catalog]
    def list_user_parameters(self):
        """Get a list of user parameters. User parameters are represented as dictionary objects.

        :return: list of user parameters
        :rtype: list[dict]
        
        Example::
          
           >>> amda.list_user_parameters()
           [{'name': 'der', 'buildchain': '(ace_xyz_gse(0) - shiftT_(ace_xyz_gse(0),10)) / shiftT_(ace_xyz_gse(0),10)', 'timestep': '1', 'dim_1': '1', 'dim_2': '1', 'id': 'ws_0'}, {'name': 'zaaaa', 'buildchain': 'imf(0)*2', 'timestep': '16', 'dim_1': '1', 'dim_2': '1', 'id': 'ws_1'}]

        .. warning::
           Calling :meth:`~speasy.amda.amda.AMDA.get_user_parameter` without having defined AMDA
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # check for authentication
        username, password=ConfigEntry("AMDA", "username").get(), ConfigEntry("AMDA","password").get()
        # get list of private parameters
        l = self.METHODS["REST"].get_user_parameters(userID=username,password=password).strip()
        d=xmltodict.parse("<root>{}</root>".format(l),attr_prefix="")
        t=requests.get(d["root"]["UserDefinedParameters"]).text
        tree=etree.parse(io.StringIO(t), parser=etree.XMLParser(recover=True))
        pp=[e.attrib for e in tree.iter(tag="param")]
        for p in pp:
            for k in p:
                if k.endswith("}id"):
                    v=p[k]
                    del p[k]
                    p["id"]=v
        return [dict(d) for d in pp]
    def list_timetables(self):
        """Get list of public timetables.

        :return: list of timetable IDs.
        :rtype: list[str]

        Example::

            >>> for timetable_id in amda.list_timetables():
            >>>     print(timetable_id)
            sharedtimeTable_0
            ...
            sharedtimeTable_139

        """
        return [t for t in self.timeTable]
    def list_datasets(self):
        """Get list of dataset id available in AMDA

        :return: list if dataset ids
        :rtype: list[str]

        Example::

            >>> for dataset_id in amda.list_datasets():
            >>>     print(dataset_id)
            ace-imf-all
            ...
            wnd-swe-kp

        """
        return [k for k in self.dataset]
    def get_product_type(self, product_id):
        """Get product type.

        :param product_id: product id
        :type product_id: str
        :return: Type of product
        :rtype: speasy.amda.amda.ProductType

        Example::
            >>> amda.get_product_type("imf")
            <ProductType.PARAMETER: 2>
            >>> amda.get_product_type("ace-imf-all")
            <ProductType.DATASET: 1>


        """
        if product_id in self.dataset:
            return ProductType.DATASET
        if product_id in self.parameter:
            return ProductType.PARAMETER
        if product_id in self.component:
            return ProductType.COMPONENT
        return ProductType.UNKNOWN

