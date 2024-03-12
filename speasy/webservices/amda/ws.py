"""
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from ._impl import is_private, is_public
from .inventory import to_xmlid
from .utils import get_parameter_args
from ...config import amda as amda_cfg
from ...core import AllowedKwargs, make_utc_datetime
from ...core.http import is_server_up
from ...core.cache import CACHE_ALLOWED_KWARGS, Cacheable, CacheCall
from ...core.dataprovider import (GET_DATA_ALLOWED_KWARGS, DataProvider,
                                  ParameterRangeCheck)
from ...core.datetime_range import DateTimeRange
from ...core.inventory.indexes import (CatalogIndex, ComponentIndex,
                                       DatasetIndex, ParameterIndex,
                                       SpeasyIndex, TimetableIndex)
from ...core.proxy import PROXY_ALLOWED_KWARGS, GetProduct, Proxyfiable
from ...products.catalog import Catalog
from ...products.dataset import Dataset
from ...products.timetable import TimeTable
from ...products.variable import SpeasyVariable

log = logging.getLogger(__name__)


def _amda_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    output_format: str = kwargs.get('output_format', 'csv')
    if output_format.lower() == 'cdf_istp':
        return f"{prefix}/{product}-cdf_istp/{start_time}"
    else:
        return f"{prefix}/{product}/{start_time}"


class ProductType(Enum):
    """Enumeration of the type of products available in AMDA_Webservice.
    """
    UNKNOWN = 0
    DATASET = 1
    PARAMETER = 2
    COMPONENT = 3
    TIMETABLE = 4
    CATALOG = 5


def _is_user_prod(product_id: str or SpeasyIndex, collection: Dict):
    xmlid = to_xmlid(product_id)
    if xmlid in collection:
        return is_private(collection[xmlid])
    return False


class AMDA_Webservice(DataProvider):
    __datetime_format__ = "%Y-%m-%dT%H:%M:%S.%f"
    """AMDA_Webservice connexion class. This class manages the connexion to AMDA_Webservice. Use the :meth:`get_data` or
    :meth:`get_parameter` methods for retrieving data.

    Methods
    -------
    is_server_up:
        Check if AMDA Webservice is up.
    product_version:
        Get date of last modification of dataset or parameter.
    get_data:
        Get product data by id
    get_user_parameter:
        Get user parameter. Raises an exception if user is not authenticated.
    get_user_timetable:
    get_user_catalog:
    get_parameter:
        Get parameter data by id.
    get_dataset:
        Get dataset contents. Returns list of SpeasyVariable objects, one for each parameter in the dataset.
    get_timetable:
        Get timetable data by ID.
    get_catalog:
        Retrieve catalog from given ID.
    parameter_range:
        Get product time range.
    list_parameters:
        Get the list of parameter indexes available in AMDA_Webservice.
    list_catalogs:
        Get the list of public catalog IDs.
    list_user_timetables:
    list_user_catalogs:
    list_user_parameters:
    list_timetables:
    list_datasets:

    Notes
    -----
    Do not create an instance of this class unless you really know what you are doing, use `speasy.amda` instance instead.


    """

    def __init__(self, server_url: str = amda_cfg.entry_point()):
        from ._impl import AmdaImpl
        self._impl = AmdaImpl(server_url=server_url)
        DataProvider.__init__(self, provider_name='amda')

    def __del__(self):
        pass

    @staticmethod
    def is_server_up(server_url: str = amda_cfg.entry_point()) -> bool:
        """Check if AMDA Webservice is up by sending a dummy request to the AMDA Webservice URL with a short timeout.

        Parameters
        ----------
        server_url: str
            AMDA Webservice URL, default is https://amda.irap.omp.eu

        Returns
        -------
        bool
            True if AMDA Webservice is up, False otherwise.

        """
        from ._impl import AmdaImpl
        return AmdaImpl.is_server_up(server_url=server_url)

    def build_inventory(self, root: SpeasyIndex):
        return self._impl.build_inventory(root)

    def build_private_inventory(self, root: SpeasyIndex):
        return self._impl.build_private_inventory(root)

    def is_user_catalog(self, catalog_id: str or CatalogIndex):
        return _is_user_prod(catalog_id, self.flat_inventory.catalogs)

    def is_user_timetable(self, timetable_id: str or TimetableIndex):
        return _is_user_prod(timetable_id, self.flat_inventory.timetables)

    def is_user_parameter(self, parameter_id: str or ParameterIndex):
        return _is_user_prod(parameter_id, self.flat_inventory.parameters)

    def has_time_restriction(self, product_id: str or SpeasyIndex, start_time: str or datetime,
                             stop_time: str or datetime):
        """Check if product is restricted for a given time range.

        Parameters
        ----------
        product_id: str or SpeasyIndex
            product id
        start_time: str or datetime
            desired data start time
        stop_time: str or datetime
            desired data stop time

        Returns
        -------
        bool
            True if product is restricted for the given time range, False otherwise.
        """
        dataset = self._find_parent_dataset(product_id)
        if dataset:
            dataset = self.flat_inventory.datasets[dataset]
            if hasattr(dataset, 'timeRestriction'):
                lower = make_utc_datetime(dataset.timeRestriction)
                upper = make_utc_datetime(dataset.stop_date)
                if lower < upper:
                    return DateTimeRange(lower, upper).intersect(
                        DateTimeRange(start_time, stop_time))
        return False

    def product_version(self, parameter_id: str or ParameterIndex):
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
        return self.flat_inventory.datasets[dataset].lastUpdate

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
        >>> spz.amda.parameter_range("imf")
        <DateTimeRange: 1997-09-02T00:00:12+00:00 -> ...>
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
        >>> spz.amda.dataset_range("ace-imf-all")
        <DateTimeRange: 1997-09-02T00:00:12+00:00 -> ...>
        """

        return self._dataset_range(dataset_id)

    def get_data(self, product, start_time=None, stop_time=None,
                 **kwargs) -> Optional[Union[SpeasyVariable, TimeTable, Catalog, Dataset]]:
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
        >>> print(imf_data.values.shape)
        (1050, 3)


        """
        product_t = self.product_type(product)
        if product_t == ProductType.DATASET and start_time and stop_time:
            return self.get_dataset(dataset_id=product, start=start_time, stop=stop_time, **kwargs)
        if product_t == ProductType.PARAMETER and start_time and stop_time:
            if self.is_user_parameter(product):
                return self.get_user_parameter(parameter_id=product, start_time=start_time, stop_time=stop_time,
                                               **kwargs)
            else:
                return self.get_parameter(product=product, start_time=start_time, stop_time=stop_time, **kwargs)
        if product_t == ProductType.CATALOG:
            if self.is_user_catalog(product):
                return self.get_user_catalog(catalog_id=product, **kwargs)
            else:
                return self.get_catalog(catalog_id=product, **kwargs)
        if product_t == ProductType.TIMETABLE:
            if self.is_user_timetable(product):
                return self.get_user_timetable(timetable_id=product, **kwargs)
            else:
                return self.get_timetable(timetable_id=product, **kwargs)
        raise ValueError(f"Unknown product: {product}")

    def get_user_parameter(self, parameter_id: str or ParameterIndex, start_time: datetime or str,
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
        >>> user_param = spz.amda.get_user_parameter("ws_0", "2019-02-24T19:20:05", "2019-02-25") # doctest: +SKIP
        >>> print(user_param.columns) # doctest: +SKIP
        ['ws_test_param']
        >>> print(user_param.values.shape) # doctest: +SKIP
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

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
    def get_user_timetable(self, timetable_id: str or TimetableIndex) -> Optional[TimeTable]:
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
        >>> spz.amda.get_user_timetable("tt_0") # doctest: +SKIP
        <TimeTable: test_alexis>

        Warnings
        --------
            Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_timetable` without having defined AMDA_Webservice
            login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
            exception being raised.

        """
        timetable_id = to_xmlid(timetable_id)
        return self._impl.dl_user_timetable(timetable_id=timetable_id)

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
    def get_user_catalog(self, catalog_id: str or CatalogIndex) -> Optional[Catalog]:
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
        >>> spz.amda.get_user_catalog("tt_0") # doctest: +SKIP
        <Catalog: test_alexis>

        Warnings
        --------
            Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_catalog` without having defined AMDA_Webservice
            login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
            exception being raised.

        """
        catalog_id = to_xmlid(catalog_id)
        return self._impl.dl_user_catalog(catalog_id=catalog_id)

    def get_parameter(self, product, start_time, stop_time,
                      extra_http_headers: Dict or None = None, output_format: str or None = None, **kwargs) -> Optional[
        SpeasyVariable]:
        if self.has_time_restriction(product, start_time, stop_time):
            kwargs['disable_proxy'] = True
            kwargs['restricted_period'] = True
            return self._get_parameter(product, start_time, stop_time, extra_http_headers=extra_http_headers,
                                       output_format=output_format or amda_cfg.output_format(), **kwargs)
        else:
            return self._get_parameter(product, start_time, stop_time, extra_http_headers=extra_http_headers,
                                       output_format=output_format or amda_cfg.output_format(), **kwargs)

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS + ['output_format', 'restricted_period'])
    @ParameterRangeCheck()
    @Cacheable(prefix="amda", version=product_version, fragment_hours=lambda x: 12, entry_name=_amda_cache_entry_name)
    @Proxyfiable(GetProduct, get_parameter_args)
    def _get_parameter(self, product, start_time, stop_time,
                       extra_http_headers: Dict or None = None, output_format: str or None = None,
                       restricted_period=False, **kwargs) -> \
        Optional[
            SpeasyVariable]:
        """Get parameter data.

        Parameters
        ----------
        product: str or AMDAParameterIndex
            parameter id
        start_time:
            desired data start time
        stop_time:
            desired data stop time
        extra_http_headers: dict
            reserved for internal use
        output_format: str
            request output format in case of success, allowed values are ASCII and CDF_ISTP

        Returns
        -------
        Optional[SpeasyVariable]
            product data if available

        Examples
        --------

        >>> import speasy as spz
        >>> import datetime
        >>> imf_data = spz.amda.get_parameter("imf", "2018-01-01", "2018-01-01T01")
        >>> print(imf_data.columns)
        ['imf[0]', 'imf[1]', 'imf[2]']
        >>> print(imf_data.values.shape)
        (225, 3)

        """
        log.debug(f'Get data: product = {product}, data start time = {start_time}, data stop time = {stop_time}')
        return self._impl.dl_parameter(start_time=start_time, stop_time=stop_time, parameter_id=product,
                                       extra_http_headers=extra_http_headers,
                                       output_format=output_format,
                                       restricted_period=restricted_period)

    def get_dataset(self, dataset_id: str or DatasetIndex, start: str or datetime, stop: str or datetime,
                    **kwargs) -> Dataset or None:
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
        Dataset or None
            dataset content as a collection of SpeasyVariable if it succeeds or None

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
        ds_range = self.dataset_range(dataset_id)
        if not ds_range.intersect(DateTimeRange(start, stop)):
            log.warning(f"You are requesting {dataset_id} outside of its definition range {ds_range}")
            return None

        dataset_id = to_xmlid(dataset_id)
        name = self.flat_inventory.datasets[dataset_id].name
        meta = {k: v for k, v in self.flat_inventory.datasets[dataset_id].__dict__.items() if
                not isinstance(v, SpeasyIndex)}
        parameters = self.list_parameters(dataset_id)
        return Dataset(name=name,
                       variables={p.name: self.get_parameter(p, start, stop, **kwargs) for p in parameters},
                       meta=meta)

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
    def get_timetable(self, timetable_id: str or TimetableIndex, **kwargs) -> Optional[TimeTable]:
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

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
    def get_catalog(self, catalog_id: str or CatalogIndex, **kwargs) -> Optional[Catalog]:
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
        >>> spz.amda.get_catalog("sharedcatalog_22")
        <Catalog: model_regions_plasmas_mms_2019>

        """
        return self._impl.dl_catalog(to_xmlid(catalog_id), **kwargs)

    def list_parameters(self, dataset_id: Optional[str or DatasetIndex] = None) -> List[ParameterIndex]:

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
        >>> amda_parameters = spz.amda.list_parameters()
        >>> len(amda_parameters) > 0
        True
        >>> amda_parameters[0]
        <ParameterIndex: ...>


        """

        if dataset_id is not None:
            return list(self.flat_inventory.datasets[to_xmlid(dataset_id)])
        return list(filter(is_public, self.flat_inventory.parameters.values()))

    def list_catalogs(self) -> List[CatalogIndex]:
        """Get the list of public catalog IDs:

        Returns
        -------
        List[AMDACatalogIndex]
            list of catalog IDs

        Examples
        --------

        >>> import speasy as spz
        >>> amda_catalogs = spz.amda.list_catalogs()
        >>> len(amda_catalogs) > 0
        True
        >>> amda_catalogs[0]
        <CatalogIndex: model_regions_plasmas_mms_2019>

        """
        return list(filter(is_public, self.flat_inventory.catalogs.values()))

    def list_user_timetables(self) -> List[TimetableIndex]:
        """Get the list of user timetables. User timetable are represented as dictionary objects.

        Returns
        -------
        List[AMDATimetableIndex]
            list of user timetables.

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_user_timetables() # doctest: +SKIP
        [<TimetableIndex: test_alexis>, <TimetableIndex: test_alexis2>, <TimetableIndex: tt3>]

        Warnings
        --------
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_timetables` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, self.flat_inventory.timetables.values()))

    def list_user_catalogs(self) -> List[CatalogIndex]:
        """Get the list of user catalogs. User catalogs are represented as dictionary objects.

        Returns
        -------
        List[AMDACatalogIndex]
            list of user catalogs.

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_user_catalogs() # doctest: +SKIP
        [<CatalogIndex: MyCatalog>]

        Warnings
        --------
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_catalogs` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, self.flat_inventory.catalogs.values()))

    def list_user_parameters(self) -> List[ParameterIndex]:
        """Get the list of user parameters. User parameters are represented as dictionary objects.

        Returns
        -------
        List[AMDAParameterIndex]
            list of user parameters

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_user_parameters() # doctest: +SKIP
        [<ParameterIndex: test_param>]

        Warnings
        --------
           Calling :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_parameter` without having defined AMDA_Webservice
           login credentials will result in a :class:`~speasy.config.exceptions.UndefinedConfigEntry`
           exception being raised.


        """
        # get list of private parameters
        return list(filter(is_private, self.flat_inventory.parameters.values()))

    def list_timetables(self) -> List[TimetableIndex]:
        """Get list of public timetables.

        Returns
        -------
        List[AMDATimetableIndex]
            list of timetable IDs.

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.list_timetables()[::50]
        [<TimetableIndex: ...>, <TimetableIndex: ...>, <TimetableIndex: ...>]

        """
        return list(filter(is_public, self.flat_inventory.timetables.values()))

    def list_datasets(self) -> List[DatasetIndex]:
        """Get the list of dataset id available in AMDA_Webservice

        Returns
        -------
        List[AMDADatasetIndex]
            list if dataset ids

        Examples
        --------

        >>> import speasy as spz
        >>> amda_datasets = spz.amda.list_datasets()
        >>> len(amda_datasets) > 0
        True
        >>> amda_datasets[0]
        <DatasetIndex: ...>
        >>> amda_datasets[0].desc
        '...'

        """
        return list(filter(is_public, self.flat_inventory.datasets.values()))

    def _find_parent_dataset(self, product_id: str or DatasetIndex or ParameterIndex or ComponentIndex) -> Optional[
        str]:

        product_id = to_xmlid(product_id)
        product_type = self.product_type(product_id)
        if product_type is ProductType.DATASET:
            return product_id
        elif product_type in (ProductType.COMPONENT, ProductType.PARAMETER):
            for dataset in self.flat_inventory.datasets.values():
                if product_id in dataset:
                    return to_xmlid(dataset)

    def product_type(self, product_id: str or SpeasyIndex) -> ProductType:
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
        if product_id in self.flat_inventory.datasets:
            return ProductType.DATASET
        if product_id in self.flat_inventory.parameters:
            return ProductType.PARAMETER
        if product_id in self.flat_inventory.components:
            return ProductType.COMPONENT
        if product_id in self.flat_inventory.timetables:
            return ProductType.TIMETABLE
        if product_id in self.flat_inventory.catalogs:
            return ProductType.CATALOG

        return ProductType.UNKNOWN
