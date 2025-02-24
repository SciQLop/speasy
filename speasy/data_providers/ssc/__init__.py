# -*- coding: utf-8 -*-

"""cda package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import xml.etree.ElementTree as ET

import numpy as np

from speasy.core import EnsureUTCDateTime
from speasy.core.cache import Cacheable, CacheCall, CACHE_ALLOWED_KWARGS
from speasy.core.dataprovider import DataProvider, ParameterRangeCheck, GET_DATA_ALLOWED_KWARGS
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
from speasy.core.requests_scheduling import SplitLargeRequests
from speasy.products.variable import SpeasyVariable, VariableTimeAxis, DataContainer
from ...core import AllowedKwargs, http


def drop_namespace(xml):
    for elem in xml.iter():
        tag_elements = elem.tag.split("}")

        # Removing name spaces and attributes
        elem.tag = tag_elements[1]
        elem.attrib.clear()
    return xml


def parse_inventory(inventory: str):
    xml = drop_namespace(ET.fromstring(inventory))
    return [
        {
            item.tag: item.text
            for item in obs
        }
        for obs in xml.findall('Observatory')
    ]


log = logging.getLogger(__name__)


def _is_valid(xml):
    result = xml.find('Result')
    return result.find('StatusCode').text.lower() == 'success' and result.find(
        'StatusSubCode').text.lower() == 'success'


def parse_trajectory(trajectory: str) -> Optional[SpeasyVariable]:
    xml = drop_namespace(ET.fromstring(trajectory))
    if _is_valid(xml):
        data = xml.find('Result').find('Data')
        coordinates = data.find('Coordinates')
        values = np.array(
            [list(map(lambda v: float(v.text), coordinates.findall(axis))) for axis in ('X', 'Y', 'Z')]).transpose()
        time_axis = np.array([np.datetime64(v.text[:-1], 'ns') for v in data.findall('Time')])
        return SpeasyVariable(
            axes=[VariableTimeAxis(values=time_axis)],
            values=DataContainer(values,
                                 meta={'CoordinateSystem': coordinates.find('CoordinateSystem').text.upper(),
                                       'UNITS': 'km'}),
            columns=['X', 'Y', 'Z']
        )
    return None


def _make_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    return f"{prefix}/{product}/{kwargs.get('coordinate_system', 'gse')}/{start_time}"


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"sscweb/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}', 'coordinate_system': kwargs.get('coordinate_system', 'gse')}


def make_index(meta: Dict):
    name = meta.pop('Name')
    meta['start_date'] = meta.pop('StartTime')
    meta['stop_date'] = meta.pop('EndTime')
    node = ParameterIndex(name=name, provider="ssc", uid=meta['Id'], meta=meta)
    return node


class SscWebservice(DataProvider):
    BASE_URL = "https://sscweb.gsfc.nasa.gov"

    def __init__(self):
        self.__url = f"{self.BASE_URL}/WS/sscr/2"
        DataProvider.__init__(self, provider_name='ssc', provider_alt_names=['sscweb'])

    def build_inventory(self, root: SpeasyIndex):
        inv = list(map(make_index, self.get_observatories()))
        root.Trajectories = SpeasyIndex(name='Trajectories', provider='ssc', uid='Trajectories',
                                        meta={item.Id: item for item in inv})
        return root

    @CacheCall(cache_retention=7 * 24 * 60 * 60, is_pure=True)
    def get_observatories(self):
        res = http.get(f"{self.__url}/observatories", headers={"Accept": "application/xml"})
        if not res.ok:
            return None
        return parse_inventory(res.text)

    def version(self, product):
        return 4

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
        >>> spz.ssc.parameter_range("solarorbiter")
        <DateTimeRange: 2020-02-10T04:56:30+00:00 -> ...>

        """
        return self._parameter_range(parameter_id)

    def get_data(self, product: str, start_time: datetime, stop_time: datetime, coordinate_system: str = 'gse',
                 debug=False, **kwargs) -> Optional[SpeasyVariable]:
        var = self._get_orbit(product=product, start_time=start_time, stop_time=stop_time,
                              coordinate_system=coordinate_system, debug=debug, **kwargs)
        return var

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS + ['coordinate_system',
                                                                                 'debug'])
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @Cacheable(prefix="ssc_orbits", fragment_hours=lambda x: 24, version=version, entry_name=_make_cache_entry_name)
    @SplitLargeRequests(threshold=lambda x: timedelta(days=60))
    @Proxyfiable(GetProduct, get_parameter_args)
    def _get_orbit(self, product: str, start_time: datetime, stop_time: datetime, coordinate_system: str = 'gse',
                   debug=False, extra_http_headers: Dict or None = None) -> Optional[SpeasyVariable]:
        if stop_time - start_time < timedelta(days=1):
            stop_time += timedelta(days=1)
        url = f"{self.__url}/locations/{product}/{start_time.strftime('%Y%m%dT%H%M%SZ')},{stop_time.strftime('%Y%m%dT%H%M%SZ')}/{coordinate_system.lower()}/"
        log.debug(f"Requesting {url}")
        headers = {"Accept": "application/xml"}
        if extra_http_headers is not None:
            headers.update(extra_http_headers)
        res = http.get(url, headers=headers)
        if res.ok:
            maybe_var = parse_trajectory(res.text)
            if maybe_var is not None:
                return maybe_var[start_time:stop_time]
        return None
