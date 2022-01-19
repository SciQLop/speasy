"""
.. testsetup:: *

   import speasy
"""

from enum import Enum
from .utils import get_parameter_args
from .indexes import to_xmlid, AMDADatasetIndex, AMDAParameterIndex, AMDATimetableIndex, AMDACatalogIndex, \
    AMDAComponentIndex, AMDAIndex

from ._impl import is_public, is_private

from datetime import datetime
from typing import Optional, List, Dict, Union

# General modules
from speasy.config import amda_user_cache_retention
from speasy.core.cache import Cacheable, CacheCall, CACHE_ALLOWED_KWARGS
from speasy.core.datetime_range import DateTimeRange
from ...core import make_utc_datetime, AllowedKwargs
from speasy.products.variable import SpeasyVariable
from speasy.products.dataset import Dataset
from speasy.products.timetable import TimeTable
from speasy.products.catalog import Catalog
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
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

        Parameters
        ----------
        parameter_id: str or AMDAParameterIndex
            parameter id

        Returns
        -------
        str
            product version
        """
        dataset = self._find_parent_dataset(parameter_id)
        return flat_inventories.amda.datasets[dataset].lastUpdate

    def get_data(self, product, start_time=None, stop_time=None, **kwargs) -> Optional[Union[
        SpeasyVariable, TimeTable, Catalog, Dataset]]:
        """Get product data by id.

        Parameters
        ----------
        product: str or AMDAIndex
            product id
        start_time: str or datetime.datetime
            desired data start time
        stop_time: str datetime.datetime
            desired data stop time

        Returns
        -------
        Optional[Union[SpeasyVariable, TimeTable, Catalog, Dataset]]
            product data if available

        Examples
        --------

        >>> import speasy as spz
        >>> imf_data = spz.amda.get_data("imf", "2019-02-24T19:20:05", "2019-02-25")
        >>> print(imf_data.columns)
        ['imf[0]', 'imf[1]', 'imf[2]']
        >>> print(imf_data.data.shape)
        (1050, 3)


        """
        product_t = self.product_type(product)
        if product_t == ProductType.DATASET and start_time and stop_time:
            return self.get_dataset(dataset_id=product, start=start_time, stop=stop_time, **kwargs)
        if product_t == ProductType.PARAMETER and start_time and stop_time:
            if is_user_parameter(product):
                return self.get_user_parameter(parameter_id=product, start_time=start_time, stop_time=stop_time,
                                               **kwargs)
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
                           stop_time: datetime or str) -> Optional[SpeasyVariable]:
        """Get user parameter. Raises an exception if user is not authenticated.

        Parameters
        ----------
        parameter_id: str or AMDAParameterIndex
            parameter id
        start_time: datetime or str
            begining of data time
        stop_time: datetime or str
            end of data time

        Returns
        -------
        Optional[SpeasyVariable]
            user parameter

        Examples
        --------

        >>> import speasy as spz
        >>> user_param = spz.amda.get_user_parameter("ws_0", "2019-02-24T19:20:05", "2019-02-25")
        >>> print(user_param.columns)
        ['ws_test_param']
        >>> print(user_param.data.shape)
        (2, 1)


        Warnings
        --------
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

        Parameters
        ----------
        timetable_id: str
            timetable id

        Returns
        -------
        Optional[TimeTable]
            user timetable

        Examples
        --------
        >>> import speasy as spz
        >>> spz.amda.get_user_timetable("tt_0")
        <TimeTable: test_alexis>

        Warnings
        --------
            Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_timetable` without having defined AMDA_Webservice
            login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
            exception being raised.

        """
        timetable_id = to_xmlid(timetable_id)
        return self._impl.dl_user_timetable(timetable_id=timetable_id)

    @CacheCall(cache_retention=float(amda_user_cache_retention.get()))
    def get_user_catalog(self, catalog_id: str or AMDACatalogIndex) -> Optional[Catalog]:
        """Get user catalog. Raises an exception if user is not authenticated.


        Parameters
        ----------
        catalog_id: str or AMDACatalogIndex
            catalog id

        Returns
        -------
        Optional[Catalog]
            user catalog

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.get_user_catalog("tt_0")
        <Catalog: test_alexis>

        Warnings
        --------
            Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_catalog` without having defined AMDA_Webservice
            login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
            exception being raised.

        """
        catalog_id = to_xmlid(catalog_id)
        return self._impl.dl_user_catalog(catalog_id=catalog_id)

    @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + ['product', 'start_time', 'stop_time'])
    @Cacheable(prefix="amda", version=product_version, fragment_hours=lambda x: 12)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_parameter(self, product, start_time, stop_time) -> Optional[SpeasyVariable]:
        """Get parameter data.

        Parameters
        ----------
        product: str or AMDAParameterIndex
            parameter id
        start_time:
            desired data start time
        stop_time:
            desired data stop time
        kwargs: dict
            optional arguments

        Returns
        -------
        Optional[SpeasyVariable]
            product data if available

        Examples
        --------

        >>> import speasy as spz
        >>> import datetime
        >>> imf_data = spz.amda.get_parameter("imf", datetime.datetime(2000,1,1), datetime.datetime(2000,1,2))
        >>> print(imf_data.columns)
        ['imf[0]', 'imf[1]', 'imf[2]']
        >>> print(imf_data.data.shape)
        (5400, 3)

        """

        log.debug(f'Get data: product = {product}, data start time = {start_time}, data stop time = {stop_time}')
        return self._impl.dl_parameter(start_time=start_time, stop_time=stop_time, parameter_id=product)

    def get_dataset(self, dataset_id: str or AMDADatasetIndex, start: str or datetime, stop: str or datetime,
                    **kwargs) -> Dataset:
        """Get dataset contents. Returns list of SpeasyVariable objects, one for each
        parameter in the dataset.

        Parameters
        ----------
        dataset_id: str or AMDADatasetIndex
            dataset id
        start: str or datetime
            desired data start
        stop: str or datetime
            desired data end

        Returns
        -------
        Dataset
            dataset content as a collection of SpeasyVariable

        Examples
        --------

        >>> import speasy as spz
        >>> import datetime
        >>> dataset = spz.amda.get_dataset("ace-imf-all", datetime.datetime(2000,1,1), datetime.datetime(2000,1,2))
        >>> dataset
        <Dataset: final / prelim
                variables: ['|b|', 'b_gse', 'b_gsm']
                time range: <DateTimeRange: 2000-01-01T00:00:11 -> 2000-01-01T23:59:55>


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
    def get_timetable(self, timetable_id: str or AMDATimetableIndex, **kwargs) -> Optional[TimeTable]:
        """Get timetable data by ID.

        Parameters
        ----------
        timetable_id: str or TimetableIndex
            time table id

        Returns
        -------
        Optional[TimeTable]
            timetable data

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.get_timetable("sharedtimeTable_0")
        <TimeTable: FTE_c1>

        """
        return self._impl.dl_timetable(to_xmlid(timetable_id), **kwargs)

    @CacheCall(cache_retention=float(amda_user_cache_retention.get()))
    def get_catalog(self, catalog_id: str or AMDACatalogIndex, **kwargs) -> Optional[Catalog]:
        """Get catalog data by ID.

        Parameters
        ----------
        catalog_id: str or AMDACatalogIndex
            catalog id

        Returns
        -------
        Optional[Catalog]
            catalog data

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.get_catalog("sharedcatalog_0")
        <Catalog: choc_MPB_catalogue_MEX>

        """
        return self._impl.dl_catalog(to_xmlid(catalog_id), **kwargs)

    def parameter_range(self, parameter_id: str or AMDAParameterIndex or AMDADatasetIndex) -> Optional[DateTimeRange]:
        """Get product time range.

        Parameters
        ----------
        parameter_id: str or AMDAParameterIndex or AMDADatasetIndex
            parameter id

        Returns
        -------
        Optional[DateTimeRange]
            Data time range

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.parameter_range("imf")
        <DateTimeRange: 1997-09-02T00:00:12+00:00 -> 2022-01-08T23:59:56+00:00>

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

        """Get the list of parameter indexes available in AMDA or a given dataset

        Parameters
        ----------
        dataset_id: Optional[str or AMDADatasetIndex]
            optional parent dataset id

        Returns
        -------
        List[AMDAParameterIndex]
            the list of parameter indexes

        Examples
        --------

        >>> import speasy as spz
        >>> for parameter_id in spz.amda.list_parameters()[::500]:
        ...     print(parameter_id)
        <ParameterIndex: |b|>
        <ParameterIndex: h+ temperature>
        <ParameterIndex: e- : F[0-3] : flux>
        <ParameterIndex: distance helios1-sun>
        <ParameterIndex: proton_flux>
        <ParameterIndex: h+ eflux : sum on elevations>
        <ParameterIndex: flux_int>
        <ParameterIndex: Si counts>
        <ParameterIndex: b tangential>
        <ParameterIndex: el temperature>


        """
        if dataset_id is not None:
            return list(flat_inventories.amda.datasets[to_xmlid(dataset_id)])
        return list(filter(is_public, flat_inventories.amda.parameters.values()))

    def list_catalogs(self) -> List[AMDACatalogIndex]:
        """Get the list of public catalog IDs:

        Returns
        -------
        List[AMDACatalogIndex]
            list of catalog IDs

        Examples
        --------

        >>> import speasy as spz
        >>> for catalog_id in spz.amda.list_catalogs():
        ...     print(catalog_id)
        <CatalogIndex: model_regions_plasmas_mms_2019>
        <CatalogIndex: model_regions_plasmas_cluster_2005>
        <CatalogIndex: choc_MPB_catalogue_MEX>
        <CatalogIndex: BepiCoordObs_Windows_of_Opportunities>
        <CatalogIndex: cassini>
        <CatalogIndex: juno>
        <CatalogIndex: maven>
        <CatalogIndex: messenger>
        <CatalogIndex: mex>
        <CatalogIndex: psp>
        <CatalogIndex: solo>
        <CatalogIndex: vex>

        """
        return list(filter(is_public, flat_inventories.amda.catalogs.values()))

    @CacheCall(cache_retention=60 * 15)
    def list_user_timetables(self) -> List[AMDATimetableIndex]:
        """Get the list of user timetables. User timetable are represented as dictionary objects.

        Returns
        -------
        List[AMDATimetableIndex]
            list of user timetables.

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_user_timetables()
        [<TimetableIndex: test_alexis>, <TimetableIndex: test_alexis2>, <TimetableIndex: tt3>]

        Warnings
        --------
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_timetables` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, flat_inventories.amda.timetables.values()))

    @CacheCall(cache_retention=60 * 15)
    def list_user_catalogs(self) -> List[AMDACatalogIndex]:
        """Get the list of user catalogs. User catalogs are represented as dictionary objects.

        Returns
        -------
        List[AMDACatalogIndex]
            list of user catalogs.

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_user_catalogs()
        [<CatalogIndex: MyCatalog>]

        Warnings
        --------
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_catalogs` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, flat_inventories.amda.catalogs.values()))

    @CacheCall(cache_retention=60 * 15)
    def list_user_parameters(self) -> List[AMDAParameterIndex]:
        """Get the list of user parameters. User parameters are represented as dictionary objects.

        Returns
        -------
        List[AMDAParameterIndex]
            list of user parameters

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_user_parameters()
        [<ParameterIndex: test_param>]

        Warnings
        --------
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_parameter` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, flat_inventories.amda.parameters.values()))

    @staticmethod
    def list_timetables() -> List[AMDATimetableIndex]:
        """Get list of public timetables.

        Returns
        -------
        List[AMDATimetableIndex]
            list of timetable IDs.

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_timetables()[::50]
        [<TimetableIndex: FTE_c1>, <TimetableIndex: Jian_SIR_list>, <TimetableIndex: MMS_Burst_Mode_2019January>]

        """
        return list(filter(is_public, flat_inventories.amda.timetables.values()))

    @staticmethod
    def list_datasets() -> List[AMDADatasetIndex]:
        """Get the list of dataset id available in AMDA_Webservice

        Returns
        -------
        List[AMDADatasetIndex]
            list if dataset ids

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_datasets()[::300]
        [<DatasetIndex: final / prelim>, <DatasetIndex: orbit>, <DatasetIndex: flyby earth 2>, <DatasetIndex: orbit venus>]

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
        """Returns product type for any known ADMA product from its index or ID.

        Parameters
        ----------
        product_id: str or AMDAIndex
            product id

        Returns
        -------
        ProductType
            Type of product IE ProductType.DATASET, ProductType.TIMETABLE, ...

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.product_type("imf")
        <ProductType.PARAMETER: 2>
        >>> spz.amda.product_type("ace-imf-all")
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
