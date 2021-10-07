from enum import Enum
from .utils import get_parameter_args
from .indexes import to_xmlid, AMDADatasetIndex, AMDAParameterIndex, AMDATimetableIndex, AMDACatalogIndex, \
    AMDAComponentIndex, AMDAIndex

from ._impl import is_public, is_private

from datetime import datetime
from typing import Optional, List, Dict, Union

# General modules
from speasy.config import amda_user_cache_retention
from speasy.core.cache import Cacheable, CacheCall
from speasy.core.datetime_range import DateTimeRange
from ...core import make_utc_datetime
from speasy.products.variable import SpeasyVariable
from speasy.products.dataset import Dataset
from speasy.products.timetable import TimeTable
from speasy.products.catalog import Catalog
from speasy.core.proxy import Proxyfiable, GetProduct
from speasy.inventory import flat_inventories
import logging

log = logging.getLogger(__name__)


class ProductType(Enum):
    """Enumeration of the type of products available in AMDA_Webservice.
    """
    UNKNOWN = 0
    DATASET = 1
    PARAMETER = 2
    COMPONENT = 3
    TIMETABLE = 4
    CATALOG = 5


def _is_user_prod(product_id: str or AMDAIndex, collection: Dict):
    xmlid = to_xmlid(product_id)
    if xmlid in collection:
        return not collection[xmlid].is_public
    return False


def is_user_catalog(catalog_id: str or AMDACatalogIndex):
    return _is_user_prod(catalog_id, flat_inventories.amda.catalogs)


def is_user_timetable(timetable_id: str or AMDATimetableIndex):
    return _is_user_prod(timetable_id, flat_inventories.amda.timetables)


def is_user_parameter(parameter_id: str or AMDAParameterIndex):
    return _is_user_prod(parameter_id, flat_inventories.amda.parameters)


class AMDA_Webservice:
    __datetime_format__ = "%Y-%m-%dT%H:%M:%S.%f"
    """AMDA_Webservice connexion class. This class manages the connexion to AMDA_Webservice. Use the :meth:`get_data` or
    :meth:`get_parameter` methods for retrieving data.

    Methods
    -------
    product_version:
    get_data:
    get_user_parameter:
    get_user_timetable:
    get_user_catalog:
    get_parameter:
    get_dataset:
    get_timetable:
    get_catalog:
        Retrieve catalog from given ID
    parameter_range:
    list_parameters:
    list_catalogs:
    list_user_timetables:
    list_user_catalogs:
    list_user_parameters:
    list_timetables:
    list_datasets:


    """

    def __init__(self, server_url: str = "http://amda.irap.omp.eu"):
        from ._impl import AmdaImpl
        self._impl = AmdaImpl(server_url=server_url)

    def __del__(self):
        pass

    def product_version(self, parameter_id: str or AMDAParameterIndex):
        """Get date of last modification of dataset or parameter.

        :param parameter_id: parameter id
        :type parameter_id: str
        :return: product version
        :rtype: str
        """
        dataset = self._find_parent_dataset(parameter_id)
        return flat_inventories.amda.datasets[dataset].lastUpdate

    def get_data(self, product, start_time=None, stop_time=None, **kwargs) -> Optional[Union[
        SpeasyVariable, TimeTable, Catalog, Dataset]]:
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

            >>> imf_data = speasy.amda.AMDA_Webservice().get_data("imf", start, stop)
            >>> # same as
            >>> imf_data = speasy.get_data("amda/imf", start, stop)

        """
        product_t = self.product_type(product)
        if product_t == ProductType.DATASET and start_time and stop_time:
            return self.get_dataset(dataset_id=product, start=start_time, stop=stop_time, **kwargs)
        if product_t == ProductType.PARAMETER and start_time and stop_time:
            if is_user_parameter(product):
                return self.get_user_parameter(parameter_id=product, start_time=start_time, stop_time=stop_time)
            else:
                return self.get_parameter(product=product, start_time=start_time, stop_time=stop_time, **kwargs)
        if product_t == ProductType.CATALOG:
            if is_user_catalog(product):
                return self.get_user_catalog(catalog_id=product, **kwargs)
            else:
                return self.get_catalog(catalog_id=product, **kwargs)
        if product_t == ProductType.TIMETABLE:
            if is_user_timetable(product):
                return self.get_user_timetable(timetable_id=product, **kwargs)
            else:
                return self.get_timetable(timetable_id=product, **kwargs)

    def get_user_parameter(self, parameter_id: str or AMDAParameterIndex, start_time: datetime or str,
                           stop_time: datetime or str):
        """Get user parameter. Raises an exception if user is not authenticated.


        :param parameter_id: parameter id
        :type parameter_id: str
        :param start_time: begining of data time
        :type start_time: datetime.datetime or str
        :param stop_time: end of data time
        :type stop_time: datetime.datetime or str
        :return: user parameter
        :rtype: speasy.common.variable.SpeasyVariable

        Example::

           >>> amda.get_user_parameter("ws_0")
           <speasy.common.variable.SpeasyVariable object at 0x7f078a0eb6d0>

        .. warning::
            Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_parameter` without having defined AMDA_Webservice
            login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
            exception being raised.

        """
        parameter_id = to_xmlid(parameter_id)
        start_time, stop_time = make_utc_datetime(start_time), make_utc_datetime(stop_time)
        return self._impl.dl_user_parameter(parameter_id=parameter_id, start_time=start_time, stop_time=stop_time)

    @CacheCall(cache_retention=float(amda_user_cache_retention.get()))
    def get_user_timetable(self, timetable_id: str or AMDATimetableIndex) -> Optional[TimeTable]:
        """Get user timetable. Raises an exception if user is not authenticated.


        :param timetable_id: timetable id
        :type timetable: str
        :return: user timetable
        :rtype: speasy.common.variable.SpeasyVariable

        Example::

           >>> amda.get_user_timetable("tt_0")
           <speasy.common.variable.SpeasyVariable object at 0x7f078a0eb6d0>

        .. warning::
            Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_timetable` without having defined AMDA_Webservice
            login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
            exception being raised.

        """
        timetable_id = to_xmlid(timetable_id)
        return self._impl.dl_user_timetable(timetable_id=timetable_id)

    @CacheCall(cache_retention=float(amda_user_cache_retention.get()))
    def get_user_catalog(self, catalog_id: str or AMDACatalogIndex) -> Optional[Catalog]:
        """Get user catalog. Raises an exception if user is not authenticated.


        :param catalog_id: catalog id
        :type catalog_id: str
        :return: user catalog
        :rtype: speasy.common.variable.SpeasyVariable

        Example::

           >>> amda.get_user_catalog("tt_0")
           <speasy.common.variable.SpeasyVariable object at 0x7f078a0eb6d0>

        .. warning::
            Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_catalog` without having defined AMDA_Webservice
            login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
            exception being raised.

        """
        catalog_id = to_xmlid(catalog_id)
        return self._impl.dl_user_catalog(catalog_id=catalog_id)

    @Cacheable(prefix="amda", version=product_version, fragment_hours=lambda x: 12)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_parameter(self, product, start_time, stop_time) -> Optional[SpeasyVariable]:
        """Get parameter data.

        :param parameter_id: parameter id
        :type parameter_id: str
        :param start_time: desired data start time
        :type start_time: datetime.datetime
        :param stop_time: desired data stop time
        :type stop_time: datetime.datetime
        :param kwargs: optional arguments
        :type kwargs: dict
        :return: product data if available
        :rtype: SpeasyVariable

        Example::

            >>> imf_data = amda.get_parameter("imf", datetime.datetime(2000,1,1), datetime.datetime(2000,2,1))

        """

        log.debug(f'Get data: product = {product}, data start time = {start_time}, data stop time = {stop_time}')
        return self._impl.dl_parameter(start_time=start_time, stop_time=stop_time, parameter_id=product)

    def get_dataset(self, dataset_id: str or AMDADatasetIndex, start: datetime, stop: datetime, **kwargs) -> Dataset:
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
        dataset_id = to_xmlid(dataset_id)
        name = flat_inventories.amda.datasets[dataset_id].name
        meta = {k: v for k, v in flat_inventories.amda.datasets[dataset_id].__dict__.items() if
                not isinstance(v, AMDAIndex)}
        parameters = self.list_parameters(dataset_id)
        return Dataset(name=name, variables={p.name: self.get_parameter(p, start, stop, **kwargs) for p in parameters},
                       meta=meta)

    @CacheCall(cache_retention=float(amda_user_cache_retention.get()))
    def get_timetable(self, timetable_id: str or AMDATimetableIndex, **kwargs) -> TimeTable:
        """Get timetable data by ID.

        :param timetable_id: time table id
        :type timetable_id: str or TimetableIndex
        :return: timetable data
        :rtype: speasy.common.variable.SpeasyVariable

        Example::

           >>> amda.get_timetable("sharedtimeTable_0")
           <speasy.common.variable.SpeasyVariable object at 0x7efce01b3f90>

        """
        return self._impl.dl_timetable(to_xmlid(timetable_id), **kwargs)

    @CacheCall(cache_retention=float(amda_user_cache_retention.get()))
    def get_catalog(self, catalog_id: str or AMDACatalogIndex, **kwargs) -> Optional[Catalog]:
        """Get catalog data by ID.

        :param catalog_id: catalog id
        :type catalog_id: str
        :return: catalog data
        :rtype: speasy.common.variable.SpeasyVariable

        Example::

           >>> amda.get_catalog("sharedcatalog_0")
           <speasy.common.variable.SpeasyVariable object at 0x7f829cc644a0>

        """
        return self._impl.dl_catalog(to_xmlid(catalog_id), **kwargs)

    def parameter_range(self, parameter_id: str or AMDAParameterIndex or AMDADatasetIndex) -> Optional[DateTimeRange]:
        """Get product time range.

        :param parameter_id: product id
        :type parameter_id: str
        :return: Data time range
        :rtype: DateTimeRange

        Example::

           >>> amda.parameter_range("imf")
           1997-09-02T00:00:12->2021-07-24T23:59:53

        """
        if not len(flat_inventories.amda.parameters):
            self._impl.update_inventory()
        parameter_id = to_xmlid(parameter_id)
        dataset_name = self._find_parent_dataset(parameter_id)

        if dataset_name in flat_inventories.amda.datasets:
            dataset = flat_inventories.amda.datasets[dataset_name]
            return DateTimeRange(
                datetime.strptime(dataset.dataStart, '%Y-%m-%dT%H:%M:%SZ'),
                datetime.strptime(dataset.dataStop, '%Y-%m-%dT%H:%M:%SZ')
            )

    def list_parameters(self, dataset_id: Optional[str or AMDADatasetIndex] = None) -> List[AMDAParameterIndex]:

        """Get list of parameter id available in AMDA_Webservice

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
        if dataset_id is not None:
            return list(flat_inventories.amda.datasets[to_xmlid(dataset_id)])
        return list(filter(is_public, flat_inventories.amda.parameters.values()))

    def list_catalogs(self) -> List[AMDACatalogIndex]:
        """Get list of public catalog IDs:

        :return: list of catalog IDs
        :rtype: list[str]

        Example::

            >>> for catalog_id in amda.get_catalogs_xml_tree():
            >>>     print(catalog_id)
            sharedcatalog_0
            ...
            sharedcatalog_16

        """
        return list(filter(is_public, flat_inventories.amda.catalogs.values()))

    @CacheCall(cache_retention=60 * 15)
    def list_user_timetables(self) -> List[AMDATimetableIndex]:
        """Get a list of user timetables. User timetable are represented as dictionary objects.

        :return: list of user timetables.
        :rtype: list[dict]

        Example::

           >>> amda.get_user_timetables_xml_tree(,
           [{'name': 'der', 'buildchain': '(ace_xyz_gse(0) - shiftT_(ace_xyz_gse(0),10)) / shiftT_(ace_xyz_gse(0),10)', 'timestep': '1', 'dim_1': '1', 'dim_2': '1', 'id': 'ws_0'}, {'name': 'zaaaa', 'buildchain': 'imf(0)*2', 'timestep': '16', 'dim_1': '1', 'dim_2': '1', 'id': 'ws_1'}]

        .. warning::
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_timetables` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, flat_inventories.amda.timetables.values()))

    @CacheCall(cache_retention=60 * 15)
    def list_user_catalogs(self) -> List[AMDACatalogIndex]:
        """Get a list of user catalogs. User catalogs are represented as dictionary objects.

        :return: list of user catalogs.
        :rtype: list[dict]

        Example::

           >>> amda.get_user_catalogs_xml_tree(,
           {'name': 'mycata', 'intervals': '1457', 'id': 'cat_0'}

        .. warning::
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_catalogs` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, flat_inventories.amda.catalogs.values()))

    @CacheCall(cache_retention=60 * 15)
    def list_user_parameters(self) -> List[AMDAParameterIndex]:
        """Get a list of user parameters. User parameters are represented as dictionary objects.

        :return: list of user parameters
        :rtype: list[dict]

        Example::

            >>> for utt in amda.get_user_parameters_xml_tree(,:
            >>>     print(utt)
            {'name': 'output-1', 'intervals': '389', 'id': 'tt_0'}
            {'name': 'output-12', 'intervals': '389', 'id': 'tt_1'}
            {'name': 'output-newell', 'intervals': '55446', 'id': 'tt_2'}
            {'name': 'output-newell-ext', 'intervals': '55446', 'id': 'tt_3'}

        .. warning::
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_parameter` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, flat_inventories.amda.parameters.values()))

    @staticmethod
    def list_timetables() -> List[AMDATimetableIndex]:
        """Get list of public timetables.

        :return: list of timetable IDs.
        :rtype: list[str]

        Example::

            >>> for timetable_id in amda.get_timetables_xml_tree():
            >>>     print(timetable_id)
            sharedtimeTable_0
            ...
            sharedtimeTable_139

        """
        return list(filter(is_public, flat_inventories.amda.timetables.values()))

    @staticmethod
    def list_datasets() -> List[AMDADatasetIndex]:
        """Get list of dataset id available in AMDA_Webservice

        :return: list if dataset ids
        :rtype: list[str]

        Example::

            >>> for dataset_id in amda.list_datasets():
            >>>     print(dataset_id)
            ace-imf-all
            ...
            wnd-swe-kp

        """
        return list(filter(is_public, flat_inventories.amda.datasets.values()))

    @staticmethod
    def _find_parent_dataset(product_id: str or AMDADatasetIndex or AMDAParameterIndex or AMDAComponentIndex) -> \
        Optional[str]:

        product_id = to_xmlid(product_id)
        product_type = AMDA_Webservice.product_type(product_id)
        if product_type is ProductType.DATASET:
            return product_id
        elif product_type in (ProductType.COMPONENT, ProductType.PARAMETER):
            for dataset in flat_inventories.amda.datasets.values():
                if product_id in dataset:
                    return to_xmlid(dataset)

    @staticmethod
    def product_type(product_id: str or AMDAIndex) -> ProductType:
        """Get product type.

        :param product_id: product id
        :type product_id: str
        :return: Type of product
        :rtype: speasy.amda.amda.ProductType

        Example::
            >>> amda.product_type("imf")
            <ProductType.PARAMETER: 2>
            >>> amda.product_type("ace-imf-all")
            <ProductType.DATASET: 1>
        """
        product_id = to_xmlid(product_id)
        if product_id in flat_inventories.amda.datasets:
            return ProductType.DATASET
        if product_id in flat_inventories.amda.parameters:
            return ProductType.PARAMETER
        if product_id in flat_inventories.amda.components:
            return ProductType.COMPONENT
        if product_id in flat_inventories.amda.timetables:
            return ProductType.TIMETABLE
        if product_id in flat_inventories.amda.catalogs:
            return ProductType.CATALOG

        return ProductType.UNKNOWN
