# -*- coding: utf-8 -*-

"""CDA_Webservice package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from speasy.core import AllowedKwargs, http
from speasy.core.cache import _cache  # _cache is used for tests (hack...)
from speasy.core.cache import CACHE_ALLOWED_KWARGS, UnversionedProviderCache
from speasy.core.cdf import load_variable
from speasy.core.dataprovider import (GET_DATA_ALLOWED_KWARGS, DataProvider,
                                      ParameterRangeCheck)
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import (DatasetIndex, ParameterIndex,
                                           SpeasyIndex)
from speasy.core.proxy import PROXY_ALLOWED_KWARGS, GetProduct, Proxyfiable
from speasy.core.requests_scheduling import SplitLargeRequests
from speasy.core.http import urlopen_with_retry
from speasy.products.variable import SpeasyVariable

log = logging.getLogger(__name__)


class CdaWebException(BaseException):
    def __init__(self, text):
        super(CdaWebException, self).__init__(text)


def _read_cdf(url: str, variable: str) -> SpeasyVariable:
    with urlopen_with_retry(url) as remote_cdf:
        return load_variable(buffer=remote_cdf.read(), variable=variable)


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"cdaweb/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}


class CDA_Webservice(DataProvider):
    def __init__(self):
        self.__url = "https://cdaweb.gsfc.nasa.gov/WS/cdasr/1"
        DataProvider.__init__(self, provider_name='cda', provider_alt_names=['cdaweb'])

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

        if type(index_or_str) is ParameterIndex:
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
                     extra_http_headers: Dict or None = None) -> Optional[
        SpeasyVariable]:

        start_time, stop_time = start_time.strftime('%Y%m%dT%H%M%SZ'), stop_time.strftime('%Y%m%dT%H%M%SZ')
        fmt = "cdf"
        url = f"{self.__url}/dataviews/sp_phys/datasets/{http.quote(dataset, safe='')}/data/{start_time},{stop_time}/{http.quote(variable, safe='')}?format={fmt}"
        headers = {"Accept": "application/json"}
        if if_newer_than is not None:
            headers["If-Modified-Since"] = if_newer_than.ctime()
        if extra_http_headers is not None:
            headers.update(extra_http_headers)
        resp = http.get(url, headers=headers)
        log.debug(resp.url)
        if resp.status_code == 200 and 'FileDescription' in resp.json():
            return _read_cdf(resp.json()['FileDescription'][0]['Name'], variable)
        elif not resp.ok:
            if resp.status_code == 404 and "No data available" in resp.json().get('Message', [""])[0]:
                log.warning(f"Got 404 'No data available' from CDAWeb with {url}")
                return None
            raise CdaWebException(f'Failed to get data with request: {url}, got {resp.status_code} HTTP response')
        else:
            return None

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS + ['if_newer_than'])
    @ParameterRangeCheck()
    @UnversionedProviderCache(prefix="cda", fragment_hours=lambda x: 12, cache_retention=timedelta(days=7))
    @SplitLargeRequests(threshold=lambda: timedelta(days=7))
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_data(self, product, start_time: datetime, stop_time: datetime, if_newer_than: datetime or None = None,
                 extra_http_headers: Dict or None = None):
        dataset, variable = self._to_dataset_and_variable(product)
        return self._dl_variable(start_time=start_time, stop_time=stop_time, dataset=dataset,
                                 variable=variable, if_newer_than=if_newer_than, extra_http_headers=extra_http_headers)

    def get_variable(self, dataset: str, variable: str, start_time: datetime or str, stop_time: datetime or str,
                     **kwargs) -> \
        Optional[SpeasyVariable]:
        return self.get_data(f"{dataset}/{variable}", start_time, stop_time, **kwargs)
