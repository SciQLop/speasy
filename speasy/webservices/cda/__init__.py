# -*- coding: utf-8 -*-

"""CDA_Webservice package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

from typing import Optional
from datetime import datetime
import pandas as pds
from speasy.core.cache import Cacheable, CACHE_ALLOWED_KWARGS, _cache  # _cache is used for tests (hack...)
from speasy.products.variable import SpeasyVariable
from speasy.core import http, AllowedKwargs
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
import numpy as np
import logging

log = logging.getLogger(__name__)


class CdaWebException(BaseException):
    def __init__(self, text):
        super(CdaWebException, self).__init__(text)


def _read_csv(url: str, *args, **kwargs) -> SpeasyVariable:
    try:
        df = pds.read_csv(url, comment='#', index_col=0, infer_datetime_format=True, parse_dates=True)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        else:
            df.index = df.index.tz_convert('UTC')
        time = np.array([t.timestamp() for t in df.index])
        return SpeasyVariable(time=time, data=df.values, columns=[c for c in df.columns])
    except pds.io.common.EmptyDataError:
        return SpeasyVariable()


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"cdaweb/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}


class CDA_Webservice:
    def __init__(self):
        self.__url = "https://cdaweb.gsfc.nasa.gov/WS/cdasr/1"

    def get_dataviews(self):
        resp = http.get(self.__url + '/dataviews', headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        dataviews = [dv['Id'] for dv in resp.json()['DataviewDescription']]
        return dataviews

    def get_instruments(self, dataview='sp_phys', observatory=None, instrumentType=None):
        args = []
        if observatory is not None:
            args.append(f'observatory={observatory}')
        if instrumentType is not None:
            args.append(f'instrumentType={instrumentType}')
        resp = http.get(self.__url + f'/dataviews/{dataview}/instruments?' + "&".join(args),
                        headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        instruments = [instrument for instrument in resp.json()['InstrumentDescription'] if
                       instrument['Name'] != '']
        return instruments

    def get_datasets(self, dataview='sp_phys', observatoryGroup=None, instrumentType=None, observatory=None,
                     instrument=None, startDate=None, stopDate=None, idPattern=None, labelPattern=None,
                     notesPattern=None):
        args = []
        if observatory is not None:
            args.append(f'observatory={observatory}')
        if observatoryGroup is not None:
            args.append(f'observatoryGroup={observatoryGroup}')
        if instrumentType is not None:
            args.append(f'instrumentType={instrumentType}')
        if instrument is not None:
            args.append(f'instrument={instrument}')
        if startDate is not None:
            args.append(f'startDate={startDate}')
        if stopDate is not None:
            args.append(f'stopDate={stopDate}')
        if idPattern is not None:
            args.append(f'idPattern={idPattern}')
        if labelPattern is not None:
            args.append(f'labelPattern={labelPattern}')
        if notesPattern is not None:
            args.append(f'notesPattern={notesPattern}')

        resp = http.get(self.__url + f'/dataviews/{dataview}/datasets?' + "&".join(args),
                        headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        datasets = [dataset for dataset in resp.json()['DatasetDescription']]
        return datasets

    def get_variables(self, dataset, dataview='sp_phys'):
        resp = http.get(self.__url + f'/dataviews/{dataview}/datasets/{dataset}/variables',
                        headers={"Accept": "application/json"})

        if not resp.ok:
            return None
        variables = [varaible for varaible in resp.json()['VariableDescription']]
        return variables

    def _dl_variable(self,
                     dataset: str, variable: str,
                     start_time: datetime, stop_time: datetime, fmt: str = None) -> Optional[SpeasyVariable]:

        start_time, stop_time = start_time.strftime('%Y%m%dT%H%M%SZ'), stop_time.strftime('%Y%m%dT%H%M%SZ')
        loader = _read_csv
        fmt = "csv"
        url = f"{self.__url}/dataviews/sp_phys/datasets/{dataset}/data/{start_time},{stop_time}/{variable}?format={fmt}"
        headers = {"Accept": "application/json"}
        log.debug(url)
        resp = http.get(url, headers=headers)
        if resp.status_code != 200:
            raise CdaWebException(f'Failed to get data with request: {url}, got {resp.status_code} HTTP response')
        if not resp.ok or 'FileDescription' not in resp.json():
            return None
        return loader(resp.json()['FileDescription'][0]['Name'], variable)

    @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + ['product', 'start_time', 'stop_time', 'fmt'])
    @Cacheable(prefix="cda", fragment_hours=lambda x: 1)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_data(self, product, start_time: datetime, stop_time: datetime, **kwargs):
        components = product.split('/')
        return self._dl_variable(start_time=start_time, stop_time=stop_time, dataset=components[0],
                                 variable=components[1], **kwargs)

    def get_variable(self, dataset: str, variable: str, start_time: datetime or str, stop_time: datetime or str,
                     **kwargs) -> \
        Optional[SpeasyVariable]:
        return self.get_data(f"{dataset}/{variable}", start_time, stop_time, **kwargs)
