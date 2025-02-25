"""
"""
import json
import logging
import warnings
import os
from datetime import datetime
from typing import Dict, Optional

from ...config import amda as amda_cfg
from ...core import AllowedKwargs, make_utc_datetime, EnsureUTCDateTime
from ...core.http import is_server_up
from ...core.cache import CACHE_ALLOWED_KWARGS, Cacheable, CacheCall
from ...core.dataprovider import (GET_DATA_ALLOWED_KWARGS, ParameterRangeCheck)
from ...core.datetime_range import DateTimeRange
from ...core.inventory.indexes import (CatalogIndex, ParameterIndex, TemplatedParameterIndex,
                                       SpeasyIndex, TimetableIndex, ArgumentIndex)
from ...core.proxy import PROXY_ALLOWED_KWARGS, GetProduct, Proxyfiable, Version
from ...inventories import flat_inventories
from ...products.catalog import Catalog
from ...products.timetable import TimeTable
from ...products.variable import SpeasyVariable

from ...core.impex import ImpexProvider, ImpexEndpoint, to_xmlid
from ...core.impex.exceptions import BadTemplateArgDefinition

log = logging.getLogger(__name__)

amda_provider_name = 'amda'
amda_capabilities = [ImpexEndpoint.AUTH, ImpexEndpoint.OBSTREE, ImpexEndpoint.GETPARAM, ImpexEndpoint.LISTTT,
                     ImpexEndpoint.GETTT, ImpexEndpoint.LISTCAT, ImpexEndpoint.GETCAT, ImpexEndpoint.LISTPARAM,
                     ImpexEndpoint.GETSTATUS]
amda_name_mapping = {
    "dataset": "xmlid",
    "parameter": "xmlid",
    "folder": "name",
    "component": "xmlid",
    "arguments": "name",
    "argument": "key",
    "item": "key"
}

AMDA_MIN_PROXY_VERSION = Version("0.12.0")


def _amda_arguments_to_dict(index):
    if isinstance(index, SpeasyIndex):
        res = {}
        for key, value in index.__dict__.items():
            if isinstance(value, SpeasyIndex) or isinstance(value, str) and key in ['name', 'default', 'type']:
                if index.spz_name() == 'items_list':
                    key = value.key
                res[key] = _amda_arguments_to_dict(value)
        return res
    elif type(index) is not str:
        return str(index)
    return index


def _argument_fits_allowed_values(value:str, argument_desc:ArgumentIndex):
    if argument_desc.type == 'list':
        return value in list(zip(*argument_desc.choices))[1]
    return True

def _stack_level_outside_of_speasy():
    import inspect
    import speasy as spz
    level = 0
    for frame in inspect.stack():
        if os.path.dirname(spz.__file__) not in frame.filename:
            return level
        level += 1
    return level

def _amda_replace_arguments_in_template(product: TemplatedParameterIndex, product_inputs: Dict[str,str]):
    product_id = product.template
    for arg in product.spz_arguments():
        k = arg.key
        v = product_inputs.get(k)
        if v is None:
            v = arg.default
            import speasy as spz
            warnings.warn(f"""Argument {arg.key} is not provided, using default value {v}
You can set Derived Parameters inputs using:
spz.get_data("amda/{product.spz_uid()}, start_time, stop_time, product_inputs={{'{k}': '{arg.default}' }})
""", category=RuntimeWarning, stacklevel=_stack_level_outside_of_speasy())
        if arg.type == 'list' and  not _argument_fits_allowed_values(v, arg):
                raise BadTemplateArgDefinition(f"""Argument {arg.key} has value {v} which is not in the allowed values {arg.choices}""")
        product_id = product_id.replace(f'##{k}##', str(v), 1)
    return product_id


def _amda_get_real_product_id(product_id: str or SpeasyIndex, **kwargs):
    product_id = to_xmlid(product_id)
    product = flat_inventories.__dict__[amda_provider_name].parameters[product_id]
    if isinstance(product, TemplatedParameterIndex) and not hasattr(product, 'predefined'):
        product_inputs = kwargs.get('product_inputs', {})
        real_product_id = _amda_replace_arguments_in_template(product, product_inputs)
    else:
        real_product_id = product_id
    return real_product_id


def _amda_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    output_format: str = kwargs.get('output_format', 'cdf_istp')
    real_product_id = _amda_get_real_product_id(product, **kwargs)
    if output_format.lower() == 'cdf_istp':
        return f"{prefix}/{real_product_id}-cdf_istp/{start_time}"
    else:
        return f"{prefix}/{real_product_id}/{start_time}"


def _amda_get_proxy_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs) -> Dict:
    proxy_args = {'path': f"{amda_provider_name}/{product}", 'start_time': f'{start_time.isoformat()}',
                  'stop_time': f'{stop_time.isoformat()}',
                  'output_format': kwargs.get('output_format', amda_cfg.output_format.get())}
    if kwargs.get('product_inputs') and isinstance(kwargs.get('product_inputs'), Dict):
        proxy_args['product_inputs'] = json.dumps(kwargs.get('product_inputs'))
    return proxy_args


class AmdaWebservice(ImpexProvider):
    def __init__(self):
        ImpexProvider.__init__(self, provider_name=amda_provider_name, server_url=amda_cfg.entry_point() + "/php/rest",
                               max_chunk_size_days=amda_cfg.max_chunk_size_days(),
                               capabilities=amda_capabilities, name_mapping=amda_name_mapping,
                               username=amda_cfg.username(), password=amda_cfg.password(),
                               output_format=amda_cfg.output_format(), min_proxy_version=AMDA_MIN_PROXY_VERSION)

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
        parameter_id: str or ParameterIndex
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

    def get_real_product_id(self, product_id: str or SpeasyIndex, **kwargs):
        return _amda_get_real_product_id(product_id, **kwargs)

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
        return super().get_catalog(catalog_id, **kwargs)

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
    def get_user_timetable(self, timetable_id: str or TimetableIndex, **kwargs) -> Optional[TimeTable]:
        """Get user timetable. Raises an exception if user is not authenticated.

        Parameters
        ----------
        timetable_id: str or TimetableIndex
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
            login credentials will result in a :class:`~speasy.core.impex.exceptions.MissingCredentials`
            exception being raised.

        """
        return super().get_user_catalog(catalog_id)

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS +
        ['output_format', 'restricted_period', 'product_inputs'])
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @Cacheable(prefix=amda_provider_name, version=product_version, fragment_hours=lambda x: 12,
               entry_name=_amda_cache_entry_name)
    @Proxyfiable(GetProduct, _amda_get_proxy_parameter_args, min_version=AMDA_MIN_PROXY_VERSION)
    def _get_parameter(self, product, start_time, stop_time,
                       extra_http_headers: Dict or None = None, output_format: str or None = None,
                       restricted_period=False, **kwargs) -> \
        Optional[
            SpeasyVariable]:
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
        return super()._get_obs_data_tree(add_template_info=True)

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
