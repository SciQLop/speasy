# -*- coding: utf-8 -*-

"""cdaweb package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import os
from typing import Optional
from datetime import datetime
import pandas as pds
import requests
from ..cache import Cacheable, _cache # _cache is used for tests (hack...)
from ..common.variable import SpwcVariable
from ..common import cdf
from ..proxy import Proxyfiable, GetProduct
import numpy as np
import tempfile
from urllib.request import urlopen


def _read_csv(url: str, *args, **kwargs) -> SpwcVariable:
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


def _read_cdf(url: str, varname: str, *args, **kwargs) -> SpwcVariable:
    try:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            with urlopen(url) as remote_file:
                f.write(remote_file.read())
            f.close()
            var = cdf.load_cdf(f.name,varname)
            os.unlink(f.name)
            return var
    except:
        return SpwcVariable()


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"cdaweb/{product}", 'start_time': f'{start_time.isoformat()}', 'stop_time': f'{stop_time.isoformat()}'}


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

    def _dl_variable(self, dataset: str, variable: str, start_time: datetime, stop_time: datetime, fmt:str=None) -> Optional[
        SpwcVariable]:
        start_time, stop_time = start_time.strftime('%Y%m%dT%H%M%SZ'), stop_time.strftime('%Y%m%dT%H%M%SZ')
        if cdf.have_cdf and fmt != "csv":
            fmt = "cdf"
            loader = _read_cdf
        else:
            loader = _read_csv
            fmt = "csv"
        url = f"{self.__url}/dataviews/sp_phys/datasets/{dataset}/data/{start_time},{stop_time}/{variable}?format={fmt}"
        print(url)
        resp = requests.get(url, headers={"Accept": "application/json"})
        if not resp.ok or 'FileDescription' not in resp.json():
            return None
        return loader(resp.json()['FileDescription'][0]['Name'], variable)

    @Cacheable(prefix="cda", fragment_hours=lambda x: 1)
    @Proxyfiable(GetProduct, get_parameter_args)
    def get_data(self, product, start_time: datetime, stop_time: datetime, **kwargs):
        components = product.split('/')
        return self._dl_variable(start_time=start_time, stop_time=stop_time, dataset=components[0],
                                 variable=components[1], **kwargs)

    def get_variable(self, dataset: str, variable: str, start_time: datetime, stop_time: datetime, **kwargs) -> \
    Optional[SpwcVariable]:
        return self.get_data(f"{dataset}/{variable}", start_time, stop_time, **kwargs)
