"""
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from ...config import amda as amda_cfg
from ...core import AllowedKwargs, make_utc_datetime, EnsureUTCDateTime
from ...core.http import is_server_up
from ...core.cache import CACHE_ALLOWED_KWARGS, Cacheable, CacheCall
from ...core.dataprovider import (GET_DATA_ALLOWED_KWARGS, ParameterRangeCheck)
from ...core.datetime_range import DateTimeRange
from ...core.inventory.indexes import (CatalogIndex, ParameterIndex,
                                       SpeasyIndex, TimetableIndex)
from ...core.proxy import PROXY_ALLOWED_KWARGS, GetProduct, Proxyfiable
from ...products.catalog import Catalog
from ...products.timetable import TimeTable
from ...products.variable import SpeasyVariable

from ...core.impex import ImpexProvider, ImpexEndpoint


log = logging.getLogger(__name__)

amda_provider_name = 'amda'
amda_capabilities = [ImpexEndpoint.AUTH, ImpexEndpoint.OBSTREE, ImpexEndpoint.GETPARAM, ImpexEndpoint.LISTTT,
                     ImpexEndpoint.GETTT, ImpexEndpoint.LISTCAT, ImpexEndpoint.GETCAT, ImpexEndpoint.LISTPARAM,
                     ImpexEndpoint.GETSTATUS]
amda_name_mapping = {
    "dataset": "xmlid",
    "parameter": "xmlid",
    "folder": "name",
    "component": "xmlid"
}


def _amda_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    output_format: str = kwargs.get('output_format', 'cdf_istp')
    if output_format.lower() == 'cdf_istp':
        return f"{prefix}/{product}-cdf_istp/{start_time}"
    else:
        return f"{prefix}/{product}/{start_time}"


def _amda_get_proxy_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs) -> Dict:
    return {'path': f"{amda_provider_name}/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}',
            'output_format': kwargs.get('output_format', amda_cfg.output_format.get())}


class AMDA_Webservice(ImpexProvider):
    def __init__(self):
        ImpexProvider.__init__(self, provider_name=amda_provider_name, server_url=amda_cfg.entry_point()+"/php/rest",
                               max_chunk_size_days=amda_cfg.max_chunk_size_days(),
                               capabilities=amda_capabilities, name_mapping=amda_name_mapping,
                               username=amda_cfg.username(), password=amda_cfg.password(),
                               output_format=amda_cfg.output_format())

    @staticmethod
    def is_server_up():
        """Check if AMDA Webservice is up by sending a dummy request to the AMDA Webservice URL with a short timeout.

        Returns
        -------
        bool
            True if AMDA Webservice is up, False otherwise.

        """
        try:
            return is_server_up(url=amda_cfg.entry_point())
        except (Exception,):
            pass
        return False

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
        dataset = self.find_parent_dataset(product_id)
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
        dataset = self.find_parent_dataset(parameter_id)
        if hasattr(self.flat_inventory.datasets[dataset], 'lastModificationDate'):
            return self.flat_inventory.datasets[dataset].lastModificationDate
        return self.flat_inventory.datasets[dataset].lastUpdate

    @CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
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
        return super().get_timetable(timetable_id, **kwargs)

    @CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
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
        return super().get_catalog(catalog_id, **kwargs)

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
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
            login credentials will result in a :class:`~speasy.core.impex.exceptions.MissingCredentials`
            exception being raised.

        """
        return super().get_user_timetable(timetable_id)

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
    def get_user_catalog(self, catalog_id: str or CatalogIndex, **kwargs) -> Optional[Catalog]:
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
            login credentials will result in a :class:`~speasy.core.impex.exceptions.MissingCredentials`
            exception being raised.

        """
        return super().get_user_catalog(catalog_id)

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS + ['output_format', 'restricted_period'])
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @Cacheable(prefix=amda_provider_name, version=product_version, fragment_hours=lambda x: 12,
               entry_name=_amda_cache_entry_name)
    @Proxyfiable(GetProduct, _amda_get_proxy_parameter_args)
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
            request output format in case of success, only CDF_ISTP is supported for now

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
        return super()._get_parameter(product, start_time, stop_time, extra_http_headers=extra_http_headers,
                                      output_format=output_format, restricted_period=restricted_period, **kwargs)

    @CacheCall(cache_retention=24 * 60 * 60, is_pure=True)
    def _get_obs_data_tree(self) -> str or None:
        return super()._get_obs_data_tree()

    @CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
    def _get_timetables_tree(self) -> str or None:
        return super()._get_timetables_tree()

    @CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
    def _get_user_timetables_tree(self) -> str or None:
        return super()._get_user_timetables_tree()

    @CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
    def _get_catalogs_tree(self) -> str or None:
        return super()._get_catalogs_tree()

    @CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
    def _get_user_catalogs_tree(self) -> str or None:
        return super()._get_user_catalogs_tree()

    @CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
    def _get_derived_parameter_tree(self) -> str or None:
        return super()._get_derived_parameter_tree()
