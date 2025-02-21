# -*- coding: utf-8 -*-

"""CDA_Webservice package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from speasy.core import AllowedKwargs, EnsureUTCDateTime
from speasy.core import http, url_utils
from speasy.config import cdaweb as cda_cfg
from speasy.core.codecs import get_codec
from speasy.core.cache import CACHE_ALLOWED_KWARGS, UnversionedProviderCache
from speasy.core.dataprovider import (GET_DATA_ALLOWED_KWARGS, DataProvider,
                                      ParameterRangeCheck)
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import (DatasetIndex, ParameterIndex,
                                           SpeasyIndex)
from speasy.core.proxy import PROXY_ALLOWED_KWARGS, GetProduct, Proxyfiable
from speasy.core.requests_scheduling import SplitLargeRequests
from speasy.core.direct_archive_downloader import get_product as direct_archive_get_product
from speasy.products.variable import SpeasyVariable
from ._direct_archive import to_direct_archive_params

log = logging.getLogger(__name__)

_burst_regex = re.compile("(.*MMS.*FPI.*BRST.*|.*MMS.*SCM.*BRST.*)")


def _is_burst_product(product: ParameterIndex or str) -> bool:
    if isinstance(product, ParameterIndex):
        product = product.spz_uid()
    return bool(_burst_regex.match(str(product)))


def _is_virtual_parameter(product: ParameterIndex) -> bool:
    return product.__dict__.get('VIRTUAL', 'FALSE').upper() == 'TRUE'


def _large_request_max_duration(product):
    if _is_burst_product(product):
        return timedelta(hours=2)
    else:
        return timedelta(days=7)


def _cache_fragment_size(product):
    if _is_burst_product(product):
        return 2
    else:
        return 12


class CdaWebException(Exception):
    def __init__(self, text):
        super(CdaWebException, self).__init__(text)


def get_parameter_args_ws(start_time: datetime, stop_time: datetime, product: str, **_):
    return {
        'path': f"cdaweb/{product}",
        'start_time': f'{start_time.isoformat()}',
        'stop_time': f'{stop_time.isoformat()}',
        'method': 'API',
    }


class CdaWebservice(DataProvider):
    BASE_URL = "https://cdaweb.gsfc.nasa.gov"

    def __init__(self):
        self.__url = f"{self.BASE_URL}/WS/cdasr/1"
        DataProvider.__init__(self, provider_name='cda', provider_alt_names=['cdaweb'])
        self._cdf_codec = get_codec('application/x-cdf')

    def build_inventory(self, root: SpeasyIndex):
        from ._inventory_builder import build_inventory
        root = build_inventory(root=root)
        return root

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
        >>> spz.cda.parameter_range("AC_H0_MFI/BGSEc")
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
        >>> spz.cda.dataset_range("AC_H0_MFI")
        <DateTimeRange: 1997-09-02T00:00:12+00:00 -> ...>

        """
        return self._dataset_range(dataset_id)

    def _to_dataset_and_variable(self, index_or_str: ParameterIndex or str) -> Tuple[str, str]:

        if isinstance(index_or_str, ParameterIndex):
            index_or_str = index_or_str.spz_uid()

        if type(index_or_str) is str:
            if '/' in index_or_str:
                parts = index_or_str.split('/')
                if len(parts) == 2:
                    return parts[0], parts[1]
                for pos in range(1, len(parts)):
                    ds = '/'.join(parts[:pos])
                    var = '/'.join(parts[pos:])
                    if (ds in self.flat_inventory.datasets) and (index_or_str in self.flat_inventory.parameters):
                        return ds, var
                raise ValueError(
                    f"Given string is ambiguous, it contains several '/', tried all combinations but failed to find a matching dataset/variable pair in inventory: {index_or_str}")
            raise ValueError(f"Given string does not look like a CDA dataset/variable pair: {index_or_str}")
        raise TypeError(f"Wrong type for {index_or_str}, expecting a string or a SpeasyIndex, got {type(index_or_str)}")

    def _dl_variable(self,
                     dataset: str, variable: str,
                     start_time: datetime, stop_time: datetime, if_newer_than: datetime or None = None,
                     extra_http_headers: Dict or None = None) -> Optional[SpeasyVariable]:
        start_time, stop_time = start_time.strftime('%Y%m%dT%H%M%SZ'), stop_time.strftime('%Y%m%dT%H%M%SZ')
        fmt = "cdf"
        url = f"{self.__url}/dataviews/sp_phys/datasets/{url_utils.quote(dataset, safe='')}/data/{start_time},{stop_time}/{url_utils.quote(variable, safe='')}?format={fmt}"
        headers = {"Accept": "application/json"}
        if if_newer_than is not None:
            headers["If-Modified-Since"] = if_newer_than.ctime()
        if extra_http_headers is not None:
            headers.update(extra_http_headers)
        resp = http.get(url, headers=headers)
        log.debug(resp.url)
        if resp.status_code == 200 and 'FileDescription' in resp.json():
            return self._cdf_codec.load_variable(file=resp.json()['FileDescription'][0]['Name'], variable=variable)
        elif not resp.ok:
            if resp.status_code == 404 and "No data available" in resp.json().get('Message', [""])[0]:
                log.warning(f"Got 404 'No data available' from CDAWeb with {url}")
                return None
            raise CdaWebException(f'Failed to get data with request: {url}, got {resp.status_code} HTTP response')
        else:
            return None

    @UnversionedProviderCache(prefix="cda", fragment_hours=_cache_fragment_size, cache_retention=timedelta(days=7))
    @SplitLargeRequests(threshold=_large_request_max_duration)
    @Proxyfiable(GetProduct, get_parameter_args_ws)
    def _get_data_with_ws(self, product, start_time: datetime, stop_time: datetime,
                          if_newer_than: datetime or None = None,
                          extra_http_headers: Dict or None = None) -> Optional[SpeasyVariable]:
        dataset, variable = self._to_dataset_and_variable(product)
        return self._dl_variable(start_time=start_time, stop_time=stop_time, dataset=dataset,
                                 variable=variable, if_newer_than=if_newer_than, extra_http_headers=extra_http_headers)

    def _get_data_with_direct_archive(self, product, start_time: datetime, stop_time: datetime, mode_is_best: bool,
                                      if_newer_than: datetime or None = None,
                                      extra_http_headers: Dict or None = None) -> Optional[SpeasyVariable]:

        dataset, variable = self._to_dataset_and_variable(product)
        dataset = self.flat_inventory.datasets[dataset]
        if type(product) is str:
            product_index = self.flat_inventory.parameters[product]
        else:
            product_index = product
        archive_params = to_direct_archive_params(file_naming=dataset.filenaming,
                                                  subdivided_by=dataset.subdividedby,
                                                  url=dataset.url)
        log.debug(f"Trying to get {product} with direct_archive method, archive_params={archive_params}")
        if archive_params is not None and not _is_virtual_parameter(product_index):
            return direct_archive_get_product(variable=variable, start_time=start_time, stop_time=stop_time,
                                              **archive_params,
                                              master_cdf_url=dataset.mastercdf)
        else:
            if not mode_is_best:
                log.warning(f"Can't get {product} without web service, switching to web service")
            return self._get_data_with_ws(product=product, start_time=start_time, stop_time=stop_time,
                                          if_newer_than=if_newer_than, extra_http_headers=extra_http_headers)

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS + ['if_newer_than', 'method'])
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    def get_data(self, product, start_time: datetime, stop_time: datetime, if_newer_than: datetime or None = None,
                 extra_http_headers: Dict or None = None, method: Optional[str] = None, **kwargs) -> Optional[
        SpeasyVariable]:
        method = method or cda_cfg.preferred_access_method.get()
        if method.upper() in ('FILE', 'BEST'):
            return self._get_data_with_direct_archive(product=product, start_time=start_time, stop_time=stop_time,
                                                      if_newer_than=if_newer_than,
                                                      extra_http_headers=extra_http_headers,
                                                      mode_is_best=method == 'best')
        else:
            return self._get_data_with_ws(product=product, start_time=start_time, stop_time=stop_time,
                                          if_newer_than=if_newer_than, extra_http_headers=extra_http_headers, **kwargs)

    def get_variable(self, dataset: str, variable: str, start_time: datetime or str, stop_time: datetime or str,
                     **kwargs) -> \
        Optional[SpeasyVariable]:
        return self.get_data(f"{dataset}/{variable}", start_time, stop_time, **kwargs)
