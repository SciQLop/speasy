import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, List, Union
from types import SimpleNamespace
import warnings
from copy import deepcopy

import numpy as np

from ..datetime_range import DateTimeRange
from ...core.dataprovider import (DataProvider)

from ...core import make_utc_datetime

from ...core.inventory.indexes import (ComponentIndex, DatasetIndex, ParameterIndex, SpeasyIndex,
                                       TimetableIndex, CatalogIndex, TemplatedParameterIndex, AnyProductIndex)
from ...core.codecs import get_codec
from ...core.proxy import MINIMUM_REQUIRED_PROXY_VERSION
from ...products.variable import SpeasyVariable, merge, DataContainer
from ...products.catalog import Catalog
from ...products.dataset import Dataset
from ...products.timetable import TimeTable
from ...products import MaybeAnyProduct

from ...inventories import flat_inventories

from .parser import ImpexXMLParser, to_xmlid
from .client import ImpexClient, ImpexEndpoint
from .utils import load_catalog, load_timetable, is_private, is_public
from .exceptions import MissingCredentials

log = logging.getLogger(__name__)


class ImpexProductType(Enum):
    """Enumeration of the type of products available in an impex webservice.
    """
    UNKNOWN = 0
    DATASET = 1
    PARAMETER = 2
    COMPONENT = 3
    TIMETABLE = 4
    CATALOG = 5


class ImpexProvider(DataProvider):
    """ImpexProvider class. This class is the main interface to interact with the Impex data providers such as AMDA or CLWeb.
    """

    def __init__(self, provider_name: str, server_url: str, max_chunk_size_days: int = 10, capabilities: List = None,
                 username: str = "", password: str = "", name_mapping: Dict = None, output_format: str = 'CDF',
                 min_proxy_version=MINIMUM_REQUIRED_PROXY_VERSION):
        self.provider_name = provider_name
        self.server_url = server_url
        self.client = ImpexClient(capabilities=capabilities, server_url=server_url,
                                  username=username, password=password, output_format=output_format)
        if not self.client.is_alive():
            warnings.warn(f"The data provider {provider_name} appears to be under maintenance")
        self.max_chunk_size_days = max_chunk_size_days
        self.name_mapping = name_mapping
        self._cdf_codec = get_codec('application/x-cdf')
        DataProvider.__init__(self, provider_name=provider_name, min_proxy_version=min_proxy_version)

    def reset_credentials(self, username: str = "", password: str = ""):
        """Reset user credentials and update the inventory by replacing the information contained in the configuration

        Parameters
        ----------
        username: Optional[str]
            username in the related service
        password: Optional[str]
            user password in the related service

        """
        self.client.reset_credentials(username=username, password=password)
        self.update_inventory()

    def credential_are_valid(self):
        """Tels if credential are valid. It only checks they are not empty. It does not check if they are correct.

        Returns
        -------
        bool
            True if credentials are valid, False otherwise.

        """
        return self.client.credential_are_valid()

    def build_inventory(self, root: SpeasyIndex):
        """Build public inventory from the specified Impex data provider.

        Parameters
        ----------
        root: SpeasyIndex
            root index in which to add all the indexes in the data provider's inventory

        Returns
        -------
        SpeasyIndex
            root index populated with public inventory

        """
        obs_data_tree = ImpexXMLParser.parse(self._get_obs_data_tree(), self.provider_name, self.name_mapping)
        root.Parameters = SpeasyIndex(name='Parameters', provider=self.provider_name, uid='Parameters',
                                      meta=obs_data_tree.dataRoot.dataCenter.__dict__)

        if self.client.is_capable(ImpexEndpoint.GETTT):
            root.TimeTables = SpeasyIndex(name='TimeTables', provider=self.provider_name, uid='TimeTables')
            public_tt = ImpexXMLParser.parse(self._get_timetables_tree(), self.provider_name, self.name_mapping)
            if hasattr(public_tt, 'ws'):
                # CLWeb case
                shared_root = public_tt.ws.timetabList
            else:
                # AMDA case
                shared_root = public_tt.timeTableList
            root.TimeTables.SharedTimeTables = SpeasyIndex(name='SharedTimeTables', provider=self.provider_name,
                                                           uid='SharedTimeTables',
                                                           meta=shared_root.__dict__)

        if self.client.is_capable(ImpexEndpoint.GETCAT):
            root.Catalogs = SpeasyIndex(name='Catalogs', provider=self.provider_name, uid='Catalogs')
            public_cat = ImpexXMLParser.parse(self._get_catalogs_tree(), self.provider_name, self.name_mapping)
            root.Catalogs.SharedCatalogs = SpeasyIndex(name='SharedCatalogs', provider=self.provider_name,
                                                       uid='SharedCatalogs',
                                                       meta=public_cat.catalogList.__dict__)

        return root

    def build_private_inventory(self, root: SpeasyIndex):
        """Build private inventory, requires user authentication.

        Parameters
        ----------
        root: SpeasyIndex
            root index in which to add all the indexes in the data provider's inventory

        Returns
        -------
        SpeasyIndex
            root index populated with user private inventory

        """
        if self.client.credential_are_valid():
            if self.client.is_capable(ImpexEndpoint.GETTT):
                user_tt = ImpexXMLParser.parse(self._get_user_timetables_tree(),
                                               self.provider_name, self.name_mapping, is_public=False)
                if hasattr(user_tt, 'ws'):
                    # CLWeb case
                    public_root = user_tt.ws.timetabList
                else:
                    # AMDA case
                    public_root = user_tt.timetabList
                root.TimeTables.MyTimeTables = SpeasyIndex(name='MyTimeTables', provider=self.provider_name,
                                                           uid='MyTimeTables', meta=public_root.__dict__)

            if self.client.is_capable(ImpexEndpoint.GETCAT):
                user_cat = ImpexXMLParser.parse(self._get_user_catalogs_tree(), self.provider_name,
                                                self.name_mapping, is_public=False)
                root.Catalogs.MyCatalogs = SpeasyIndex(name='MyCatalogs', provider=self.provider_name, uid='MyCatalogs',
                                                       meta=user_cat.catalogList.__dict__)

            if self.client.is_capable(ImpexEndpoint.LISTPARAM):
                user_param = ImpexXMLParser.parse(self._get_derived_parameter_tree(),
                                                  self.provider_name, self.name_mapping, is_public=False)
                root.DerivedParameters = SpeasyIndex(name='DerivedParameters', provider=self.provider_name,
                                                     uid='DerivedParameters', meta=user_param.ws.paramList.__dict__)
        return root

    def parameter_range(self, parameter_id: str or ParameterIndex) -> Optional[DateTimeRange]:
        """Get parameter time range as defined in the inventory.

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
        """Get dataset time range as defined in the inventory.

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

    def is_user_catalog(self, catalog_id: str or CatalogIndex):
        """Tels if a product is a user catalog

        Parameters
        ----------
        catalog_id: str or CatalogIndex
            product id

        Returns
        -------
        bool
            True if the product is a user catalog, False otherwise.

        """
        return ImpexProvider.is_user_product(catalog_id, flat_inventories.__dict__[self.provider_name].catalogs)

    def is_user_timetable(self, timetable_id: str or TimetableIndex):
        """Tels if a product is a user timetable

        Parameters
        ----------
        timetable_id: str or TimetableIndex
            product id

        Returns
        -------
        bool
            True if the product is a user timetable, False otherwise.

        """
        return ImpexProvider.is_user_product(timetable_id, flat_inventories.__dict__[self.provider_name].timetables)

    def is_user_parameter(self, parameter_id: str or ParameterIndex):
        """Tells if a product is a user parameter

        Parameters
        ----------
        parameter_id: str or ParameterIndex
            product id

        Returns
        -------
        bool
            True if the product is a user parameter, False otherwise.

        """
        return ImpexProvider.is_user_product(parameter_id, flat_inventories.__dict__[self.provider_name].parameters)

    def get_data(self, product, start_time=None, stop_time=None,
                 **kwargs) -> MaybeAnyProduct:
        """Get product data by id, start and stop time if applicable. The product can be a parameter, a dataset, a
        catalog or a timetable. The method will automatically determine the product type and call the appropriate underlying
        method.

        Parameters
        ----------
        product: str or SpeasyIndex
            product id
        start_time: str or datetime.datetime
            desired data start time
        stop_time: str datetime.datetime
            desired data stop time

        Returns
        -------
        MaybeAnyProduct
            product data if available, None otherwise

        Examples
        --------

        >>> import speasy as spz
        >>> imf_data = spz.amda.get_data("imf", "2019-02-24T19:20:05", "2019-02-25")
        >>> print(imf_data.columns)
        ['bx', 'by', 'bz']
        >>> print(imf_data.values.shape)
        (1050, 3)


        """
        product_t = self.product_type(product)
        if product_t == ImpexProductType.DATASET and start_time and stop_time:
            return self.get_dataset(dataset_id=product, start=start_time, stop=stop_time, **kwargs)
        if product_t == ImpexProductType.PARAMETER and start_time and stop_time:
            if self.is_user_parameter(product):
                return self.get_user_parameter(parameter_id=product,
                                               start_time=start_time, stop_time=stop_time, **kwargs)
            else:
                return self.get_parameter(product=product, start_time=start_time, stop_time=stop_time, **kwargs)
        if product_t == ImpexProductType.CATALOG:
            if self.is_user_catalog(product):
                return self.get_user_catalog(catalog_id=product, **kwargs)
            else:
                return self.get_catalog(catalog_id=product, **kwargs)
        if product_t == ImpexProductType.TIMETABLE:
            if self.is_user_timetable(product):
                return self.get_user_timetable(timetable_id=product, **kwargs)
            else:
                return self.get_timetable(timetable_id=product, **kwargs)
        raise ValueError(f"Unknown product: {product}")

    def get_user_parameter(self, parameter_id: str or ParameterIndex, start_time: datetime or str,
                           stop_time: datetime or str, **kwargs) -> Optional[SpeasyVariable]:
        """Get user parameter. Raises an exception if user is not authenticated.

        Parameters
        ----------
        parameter_id: str or ParameterIndex
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
        return self._dl_user_parameter(parameter_id=parameter_id, start_time=start_time, stop_time=stop_time, **kwargs)

    def get_parameter(self, product, start_time, stop_time,
                      extra_http_headers: Dict or None = None,
                      output_format: str or None = None, **kwargs) -> Optional[SpeasyVariable]:
        """Get parameter data.

        Parameters
        ----------
        product: str or ParameterIndex
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
        ['bx', 'by', 'bz']
        >>> print(imf_data.values.shape)
        (225, 3)

        """
        if hasattr(self, 'has_time_restriction') and self.has_time_restriction(product, start_time, stop_time):
            kwargs['disable_proxy'] = True
            kwargs['restricted_period'] = True

        return self._get_parameter(product, start_time, stop_time, extra_http_headers=extra_http_headers,
                                   output_format=output_format or self.client.output_format, **kwargs)

    def get_dataset(self, dataset_id: str or DatasetIndex, start: str or datetime, stop: str or datetime,
                    **kwargs) -> Dataset or None:
        """Get dataset contents. Returns list of SpeasyVariable objects, one for each
        parameter in the dataset.

        Parameters
        ----------
        dataset_id: str or DatasetIndex
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
                time range: <DateTimeRange: 2000-01-01T00:00:11+00:00 -> 2000-01-01T23:59:55+00:00>


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
        return self._dl_timetable(to_xmlid(timetable_id), **kwargs)

    def get_catalog(self, catalog_id: str or CatalogIndex, **kwargs) -> Optional[Catalog]:
        """Get catalog data by ID.

        Parameters
        ----------
        catalog_id: str or CatalogIndex
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
        return self._dl_catalog(to_xmlid(catalog_id), **kwargs)

    def get_user_timetable(self, timetable_id: str or TimetableIndex, **kwargs) -> Optional[TimeTable]:
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
        return self._dl_user_timetable(to_xmlid(timetable_id), **kwargs)

    def get_user_catalog(self, catalog_id: str or CatalogIndex, **kwargs) -> Optional[Catalog]:
        """Get user catalog. Raises an exception if user is not authenticated.


        Parameters
        ----------
        catalog_id: str or CatalogIndex
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
        return self._dl_user_catalog(catalog_id, **kwargs)

    def product_type(self, product_id: str or SpeasyIndex) -> ImpexProductType:
        """Returns product type for any known Impex product from its index or ID.

        Parameters
        ----------
        product_id: str or SpeasyIndex
            product id

        Returns
        -------
        ImpexProductType
            Type of product IE ImpexProductType.DATASET, ImpexProductType.TIMETABLE, ...

        Examples
        --------

        >>> import speasy as spz
        >>> spz.amda.product_type("imf")
        <ImpexProductType.PARAMETER: 2>
        >>> spz.amda.product_type("ace-imf-all")
        <ImpexProductType.DATASET: 1>
        """
        product_id = to_xmlid(product_id)
        if product_id in flat_inventories.__dict__[self.provider_name].datasets:
            return ImpexProductType.DATASET
        if product_id in flat_inventories.__dict__[self.provider_name].parameters:
            return ImpexProductType.PARAMETER
        if product_id in flat_inventories.__dict__[self.provider_name].components:
            return ImpexProductType.COMPONENT
        if product_id in flat_inventories.__dict__[self.provider_name].timetables:
            return ImpexProductType.TIMETABLE
        if product_id in flat_inventories.__dict__[self.provider_name].catalogs:
            return ImpexProductType.CATALOG

        return ImpexProductType.UNKNOWN

    def to_index(self, product_id: str or SpeasyIndex) -> AnyProductIndex:
        if type(product_id) in (
            DatasetIndex, ParameterIndex, TemplatedParameterIndex, ComponentIndex, TimetableIndex, CatalogIndex):
            return product_id
        elif type(product_id) is str:
            if p := flat_inventories.__dict__[self.provider_name].datasets.get(product_id):
                return p
            if p := flat_inventories.__dict__[self.provider_name].parameters.get(product_id):
                return p
            if p := flat_inventories.__dict__[self.provider_name].components.get(product_id):
                return p
            if p := flat_inventories.__dict__[self.provider_name].timetables.get(product_id):
                return p
            if p := flat_inventories.__dict__[self.provider_name].catalogs.get(product_id):
                return p
        raise ValueError(f"Unknown product: {product_id}")

    def find_parent_dataset(
        self,
        product_id: Union[str, DatasetIndex, ParameterIndex, TemplatedParameterIndex, ComponentIndex]
    ) -> Optional[str]:

        product_id = to_xmlid(product_id)
        product = self.to_index(product_id)
        if isinstance(product, DatasetIndex):
            return product_id
        elif type(product) in (ParameterIndex, ComponentIndex, TemplatedParameterIndex):
            return product.dataset
        return None

    @staticmethod
    def is_user_product(product_id: str or SpeasyIndex, collection: Dict):
        xmlid = to_xmlid(product_id)
        if xmlid in collection:
            return is_private(collection[xmlid])
        return False

    def list_datasets(self) -> List[DatasetIndex]:
        """Get the list of datasets available

        Returns
        -------
        List[DatasetIndex]
            list of dataset indexes

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
        return list(filter(is_public, flat_inventories.__dict__[self.provider_name].datasets.values()))

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
            return list(flat_inventories.__dict__[self.provider_name].datasets[to_xmlid(dataset_id)])
        return list(filter(is_public, flat_inventories.__dict__[self.provider_name].parameters.values()))

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
        return list(filter(is_private, flat_inventories.__dict__[self.provider_name].parameters.values()))

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
        return list(filter(is_public, flat_inventories.__dict__[self.provider_name].timetables.values()))

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
        return list(filter(is_private, flat_inventories.__dict__[self.provider_name].timetables.values()))

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
        return list(filter(is_public, flat_inventories.__dict__[self.provider_name].catalogs.values()))

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
        return list(filter(is_private, flat_inventories.__dict__[self.provider_name].catalogs.values()))

    def _get_parameter(self, product, start_time, stop_time,
                       extra_http_headers: Dict or None = None, output_format: str or None = None,
                       restricted_period=False, **kwargs) -> \
        Optional[
            SpeasyVariable]:
        log.debug(f'Get data: product = {product}, data start time = {start_time}, data stop time = {stop_time}')
        if hasattr(self, 'get_real_product_id'):
            real_product_id = self.get_real_product_id(product, **kwargs)
            if real_product_id:
                kwargs['real_product_id'] = real_product_id
        return self._dl_parameter(start_time=start_time, stop_time=stop_time, parameter_id=product,
                                  extra_http_headers=extra_http_headers,
                                  output_format=output_format,
                                  product_variables=self._get_product_variables(product, **kwargs),
                                  restricted_period=restricted_period,
                                  time_format='UNIXTIME', **kwargs)

    def _dl_parameter_chunk(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                            extra_http_headers: Dict or None = None,
                            use_credentials: bool = False,
                            product_variables: List = None, **kwargs) -> Optional[SpeasyVariable]:
        url = self.client.get_parameter(start_time=start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                        stop_time=stop_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                        parameter_id=parameter_id,
                                        extra_http_headers=extra_http_headers,
                                        use_credentials=use_credentials, **kwargs)
        # check status until done
        if url is not None:
            var = None
            if not product_variables:
                product_variables = [kwargs.get('real_product_id', parameter_id)]
            if kwargs.get('output_format', self.client.output_format) in ["CDF_ISTP", "CDF"]:
                var = self._cdf_codec.load_variables(variables=product_variables, file=url)
            else:
                raise NotImplementedError(f"Output format {kwargs.get('output_format')} not supported")
            if var is not None:
                if isinstance(var, SpeasyVariable):
                    if len(var):
                        log.debug(
                            f'Loaded var: data shape = {var.values.shape}, data start time = {var.time[0]}, \
                                    data stop time = {var.time[-1]}')
                    else:
                        log.debug('Loaded var: Empty var')
                else:
                    if parameter_id in self.flat_inventory.parameters:
                        name = self.flat_inventory.parameters[parameter_id].spz_name()
                    else:
                        name = parameter_id
                    var = ImpexProvider._concatenate_variables(var, name)
                    if var is None:
                        log.debug('Failed to concatenate variables')
            else:
                log.debug(f'Failed to load file f{url}')
            return var
        return None

    def _dl_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                      extra_http_headers: Dict or None = None, restricted_period=False,
                      use_credentials: bool = False,
                      product_variables: List = None, **kwargs) -> Optional[SpeasyVariable]:
        dt = timedelta(days=self.max_chunk_size_days)
        if restricted_period:
            if not self.client.credential_are_valid():
                raise MissingCredentials(
                    "Restricted period requested but no credentials provided, please add your "
                    "{} credentials.".format(self.provider_name))
            else:
                use_credentials = True
        if stop_time - start_time > dt:
            var = None
            curr_t = start_time
            while curr_t < stop_time:
                var = merge([var, self._dl_parameter_chunk(curr_t, min(curr_t + dt, stop_time), parameter_id,
                                                           extra_http_headers=extra_http_headers,
                                                           product_variables=product_variables,
                                                           use_credentials=use_credentials,
                                                           **kwargs)])
                curr_t += dt
            return var
        else:
            return self._dl_parameter_chunk(start_time, stop_time, parameter_id,
                                            extra_http_headers=extra_http_headers,
                                            use_credentials=use_credentials,
                                            product_variables=product_variables, **kwargs)

    def _dl_user_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                           **kwargs) -> Optional[SpeasyVariable]:
        return self._dl_parameter(parameter_id=parameter_id, start_time=start_time, stop_time=stop_time,
                                  product_variables=self._get_product_variables(parameter_id, **kwargs),
                                  use_credentials=True, **kwargs)

    def _dl_timetable(self, timetable_id: str, use_credentials=False, **kwargs):
        get_timetable_url = self.client.get_timetable(timetable_id, use_credentials=use_credentials, **kwargs)
        if get_timetable_url is not None:
            timetable = load_timetable(filename=get_timetable_url)
            if timetable:
                timetable.meta.update(
                    flat_inventories.__dict__[self.provider_name].timetables.get(timetable_id,
                                                                                 SimpleNamespace()).__dict__)
                log.debug(f'Loaded timetable: id = {timetable_id}')  # lgtm[py/clear-text-logging-sensitive-data]
            else:
                log.debug('Got None')
            return timetable
        return None

    def _dl_user_timetable(self, timetable_id: str, **kwargs):
        return self._dl_timetable(timetable_id, use_credentials=True, **kwargs)

    def _dl_catalog(self, catalog_id: str, use_credentials=False, **kwargs):
        get_catalog_url = self.client.get_catalog(catalog_id, use_credentials=use_credentials, **kwargs)
        if get_catalog_url is not None:
            catalog = load_catalog(get_catalog_url)
            if catalog:
                log.debug(f'Loaded catalog: id = {catalog_id}')  # lgtm[py/clear-text-logging-sensitive-data]
                catalog.meta.update(
                    flat_inventories.__dict__[self.provider_name].catalogs.get(catalog_id, SimpleNamespace()).__dict__)
            else:
                log.debug('Got None')
            return catalog
        return None

    def _dl_user_catalog(self, catalog_id: str, **kwargs):
        return self._dl_catalog(catalog_id, use_credentials=True, **kwargs)

    def _get_product_variables(self, product_id: str or SpeasyIndex, **kwargs):
        product_id = to_xmlid(product_id)
        return [kwargs.get('real_product_id', product_id)]

    @staticmethod
    def _concatenate_variables(variables: Dict[str, SpeasyVariable], product_id) -> Optional[SpeasyVariable]:
        if len(variables) == 0:
            return None
        elif len(variables) == 1:
            return list(variables.values())[0]

        axes = []
        columns = []
        values = None
        meta = {}
        for name, variable in variables.items():
            if not axes:
                values = variable.values.copy()
                axes = variable.axes.copy()
                meta = deepcopy(variable.meta)
            else:
                values = np.concatenate((values, variable.values), axis=1)
                axes += [axis.copy() for axis in variable.axes[1:]]
            columns.append(name)

        if 'FIELDNAM' in meta:
            meta['FIELDNAM'] = product_id

        return SpeasyVariable(
            axes=axes,
            values=DataContainer(values=values, meta=meta, name=product_id, is_time_dependent=True),
            columns=columns)

    def _get_obs_data_tree(self, add_template_info=False) -> str or None:
        return self.client.get_obs_data_tree(add_template_info=add_template_info)

    def _get_timetables_tree(self) -> str or None:
        return self.client.get_time_table_list()

    def _get_catalogs_tree(self) -> str or None:
        return self.client.get_catalog_list()

    def _get_user_timetables_tree(self) -> str or None:
        return self.client.get_time_table_list(use_credentials=True)

    def _get_user_catalogs_tree(self) -> str or None:
        return self.client.get_catalog_list(use_credentials=True)

    def _get_derived_parameter_tree(self) -> str or None:
        return self.client.get_derived_parameter_list()
