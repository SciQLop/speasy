# -*- coding: utf-8 -*-

"""CDA_Webservice package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

from typing import Optional
from datetime import datetime
from speasy.core.cache import Cacheable, CACHE_ALLOWED_KWARGS, _cache  # _cache is used for tests (hack...)
from speasy.products.variable import SpeasyVariable
from speasy.core import http, AllowedKwargs
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
from speasy.core.cdf import load_variable
from urllib.request import urlopen
import logging
from .indexes import to_dataset_and_variable

log = logging.getLogger(__name__)


class CdaWebException(BaseException):
    def __init__(self, text):
        super(CdaWebException, self).__init__(text)


def _read_cdf(url: str, variable: str) -> SpeasyVariable:
    with urlopen(url) as remote_cdf:
        return load_variable(buffer=remote_cdf.read(), variable=variable)


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"cdaweb/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}


class CDA_Webservice:
    def __init__(self):
        self.__url = "https://cdaweb.gsfc.nasa.gov/WS/cdasr/1"

    def _dl_variable(self,
                     dataset: str, variable: str,
                     start_time: datetime, stop_time: datetime) -> Optional[SpeasyVariable]:

        start_time, stop_time = start_time.strftime('%Y%m%dT%H%M%SZ'), stop_time.strftime('%Y%m%dT%H%M%SZ')
        fmt = "cdf"
        url = f"{self.__url}/dataviews/sp_phys/datasets/{dataset}/data/{start_time},{stop_time}/{variable}?format={fmt}"
        headers = {"Accept": "application/json"}
        log.debug(url)
        resp = http.get(url, headers=headers)
        if resp.status_code != 200:
            raise CdaWebException(f'Failed to get data with request: {url}, got {resp.status_code} HTTP response')
        if not resp.ok or 'FileDescription' not in resp.json():
            return None
        return _read_cdf(resp.json()['FileDescription'][0]['Name'], variable)

    @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + ['product', 'start_time', 'stop_time'])
    @Cacheable(prefix="cda", fragment_hours=lambda x: 1)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_data(self, product, start_time: datetime, stop_time: datetime):
        dataset, variable = to_dataset_and_variable(product)
        return self._dl_variable(start_time=start_time, stop_time=stop_time, dataset=dataset,
                                 variable=variable)

    def get_variable(self, dataset: str, variable: str, start_time: datetime or str, stop_time: datetime or str,
                     **kwargs) -> \
        Optional[SpeasyVariable]:
        return self.get_data(f"{dataset}/{variable}", start_time, stop_time, **kwargs)
