# -*- coding: utf-8 -*-

"""cdaweb package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

from typing import Optional
from datetime import datetime
import pandas as pds
import requests
from ..cache import _cache
from ..common.datetime_range import DateTimeRange
from ..common.variable import SpwcVariable
from ..common import make_utc_datetime
from functools import partial
import numpy as np


def _read_csv(url: str) -> SpwcVariable:
    try:
        df = pds.read_csv(url, comment='#', index_col=0, infer_datetime_format=True, parse_dates=True)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        else:
            df.index = df.index.tz_convert('UTC')
        time = np.array([t.timestamp() for t in df.index])
        return SpwcVariable(time=time, data=df.values, columns=[c for c in df.columns])
    except pds.io.common.EmptyDataError:
        return SpwcVariable()


class cdaweb:
    def __init__(self):
        self.__url = "https://cdaweb.gsfc.nasa.gov/WS/cdasr/1"

    def get_dataviews(self):
        resp = requests.get(self.__url + '/dataviews', headers={"Accept": "application/json"})
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
        resp = requests.get(self.__url + f'/dataviews/{dataview}/instruments?' + "&".join(args),
                            headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        instruments = [instrument for instrument in resp.json()['InstrumentDescription'] if
                       instrument['Name'] != '']
        return instruments

    def get_datasets(self, dataview='sp_phys', observatoryGroup=None, instrumentType=None, observatory=None,
                     instrument=None,
                     startDate=None, stopDate=None, idPattern=None, labelPattern=None, notesPattern=None):
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

        resp = requests.get(self.__url + f'/dataviews/{dataview}/datasets?' + "&".join(args),
                            headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        datasets = [dataset for dataset in resp.json()['DatasetDescription']]
        return datasets

    def get_variables(self, dataset, dataview='sp_phys'):
        resp = requests.get(self.__url + f'/dataviews/{dataview}/datasets/{dataset}/variables',
                            headers={"Accept": "application/json"})

        if not resp.ok:
            return None
        variables = [varaible for varaible in resp.json()['VariableDescription']]
        return variables

    def _dl_variable(self, dataset: str, variable: str, start_time: datetime, stop_time: datetime) -> Optional[SpwcVariable]:
        start_time, stop_time = start_time.strftime('%Y%m%dT%H%M%SZ'), stop_time.strftime('%Y%m%dT%H%M%SZ')
        url = f"{self.__url}/dataviews/sp_phys/datasets/{dataset}/data/{start_time},{stop_time}/{variable}?format=csv"
        print(url)
        resp = requests.get(url, headers={"Accept": "application/json"})
        if not resp.ok or 'FileDescription' not in resp.json():
            return None
        return _read_csv(resp.json()['FileDescription'][0]['Name'])

    def get_variable(self, dataset: str, variable: str, start_time: datetime, stop_time: datetime) -> Optional[SpwcVariable]:
        result = None
        start_time = make_utc_datetime(start_time)
        stop_time = make_utc_datetime(stop_time)
        cache_product = f"cdaweb/{dataset}/{variable}"
        result = _cache.get_data(cache_product, DateTimeRange(start_time, stop_time),
                                 partial(self._dl_variable, dataset, variable))
        return result

    def get_data(self, path, start_time: datetime, stop_time: datetime):
        components = path.split('/')
        return self.get_variable(start_time=start_time, stop_time=stop_time, dataset=components[0], variable=components[1])
