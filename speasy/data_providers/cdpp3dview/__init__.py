# -*- coding: utf-8 -*-

"""Cdpp 3dView package for Space Physics WebServices Client."""

__author__ = """Richard Hitier"""
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import logging
from typing import List, Optional

from speasy import SpeasyVariable
from speasy.core import fix_name, http
from speasy.core.algorithms import AllowedKwargs
from speasy.core.cache._function_cache import CacheCall
from speasy.core.cache._providers_caches import (
    CACHE_ALLOWED_KWARGS,
    Cacheable,
    UnversionedProviderCache,
)
from speasy.core.codecs.codecs_registry import get_codec
from speasy.core.dataprovider import (
    GET_DATA_ALLOWED_KWARGS,
    DataProvider,
    ParameterRangeCheck,
)
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import (
    ParameterIndex,
    SpeasyIndex,
    make_inventory_node,
)
from speasy.core.proxy import PROXY_ALLOWED_KWARGS, Proxyfiable
from speasy.core.time import EnsureUTCDateTime
from speasy.core.typing import AnyDateTimeType

log = logging.getLogger(__name__)


class Cdpp3dViewWebException(Exception):
    pass


def _make_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    coordinate_frame = kwargs.get('coordinate_frame', 'J2000')
    sampling = kwargs.get('sampling', '600')
    return f"{prefix}/{product}/{coordinate_frame}/{sampling}/{start_time}"


class Cdpp3dViewWebservice(DataProvider):

    BASE_URL = "https://3dview.irap.omp.eu/webresources"

    def __init__(self):
        self._frames: List[str] = []
        self._cdf_codec = get_codec('application/x-cdf')
        DataProvider.__init__(
            self, provider_name="cdpp3dview", provider_alt_names=["cdpp3d"]
        )

    def version(self, product):
        return 1

    def _build_frames_list(self):
        URL = f"{self.BASE_URL}/get_frames"
        with http.urlopen(URL, headers={"Accept": "application/json"}) as response:
            data = response.json()
        _frames = [f["name"] for f in data['frames']]
        return _frames

    def _build_bodies_tree(self, trajectory_node: SpeasyIndex):
        bodies = self._get_bodies()

        # Group bodies by type (Spacecraft, Comet, ...)
        bodies_by_type = {}
        for body in bodies:
            body_type = body.get('type', 'SPACECRAFT')
            if body_type not in bodies_by_type:
                bodies_by_type[body_type] = []
            bodies_by_type[body_type].append(body)

        for body_type, bodies_list in bodies_by_type.items():
            type_node = make_inventory_node(
                trajectory_node,
                SpeasyIndex,
                provider="cdpp3dview",
                uid=body_type,
                name=fix_name(body_type),
                description=f"{body_type} bodies"
            )

            for body in bodies_list:
                body_name = body['name']

                make_inventory_node(
                    type_node,
                    ParameterIndex,
                    provider="cdpp3dview",
                    uid=body_name,
                    name=fix_name(body_name),
                    description=f"{body_name} trajectories",
                    start_date=body['coverage'][0],
                    stop_date=body['coverage'][1]
                )

    def build_inventory(self, root: SpeasyIndex):

        self._frames = self._build_frames_list()

        trajectory_node = make_inventory_node(
            root,
            SpeasyIndex,
            provider="cdpp3dview",
            uid="Trajectories",
            name="Trajectories",
        )
        self._build_bodies_tree(trajectory_node)

        return root

    def get_data(
        self,
        product: str,
        start_time: AnyDateTimeType,
        stop_time: AnyDateTimeType,
        coordinate_frame: str = "J2000",
        sampling: str = "600",
        if_newer_than: Optional[AnyDateTimeType] = None,
        **kwargs,
    ) -> Optional[SpeasyVariable]:
        self._frames = self.get_frames()
        if coordinate_frame not in self._frames:
            exception_msg = (
                f"Coordinate frame '{coordinate_frame}' is not available.\n"
                f"Available frames are: {self._frames}"
            )
            raise Cdpp3dViewWebException(exception_msg)

        var = self._get_trajectory(
            product=product,
            start_time=start_time,
            stop_time=stop_time,
            coordinate_frame=coordinate_frame,
            sampling=sampling,
            if_newer_than=if_newer_than,
            ** kwargs,
        )
        return var

    @UnversionedProviderCache(prefix="cdpp3dview", fragment_hours=lambda x: 24)
    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS
        + CACHE_ALLOWED_KWARGS
        + GET_DATA_ALLOWED_KWARGS
        + ["coordinate_frame", "sampling", "if_newer_than", "format"],
    )
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @Cacheable(prefix="3dview_trajectories", fragment_hours=lambda x: 24, version=version, entry_name=_make_cache_entry_name)
    # @Proxyfiable(GetProduct, get_parameter_args_ws)
    def _get_trajectory(
        self,
        product: str,
        start_time: AnyDateTimeType,
        stop_time: AnyDateTimeType,
        coordinate_frame: str,
        sampling: str = "600",
        if_newer_than: Optional[AnyDateTimeType] = None,
        format="cdf",
        **kwargs,
    ):
        body = self._to_parameter_index(product).spz_name()

        date_format = "%Y-%m-%dT%H:%M:%S"
        start_date = start_time.strftime(date_format)
        stop_date = stop_time.strftime(date_format)
        URL = (
            f"{self.BASE_URL}/get_trajectory?"
            f"body={body}&frame={coordinate_frame}&"
            f"start={start_date}&stop={stop_date}&"
            f"sampling={sampling}&format={format}"
        )
        headers = {}
        if if_newer_than is not None:
            headers["If-Modified-Since"] = if_newer_than.ctime()
        resp = http.get(URL, headers=headers)
        if resp.status_code == 200:
            return self._cdf_codec.load_variable(file=resp.bytes,
                                                 variable='pos')
        elif not resp.ok:
            if resp.status_code == 404:
                log.warning(
                    f"Got 404 'No data available' from 3dView with {URL}")
                return None
            raise Cdpp3dViewWebException(
                f'Failed to get data with request: {URL},'
                f'got {resp.status_code} HTTP response')
        else:
            return None

    def get_frames(self) -> List[str]:
        return self._frames

    def parameter_range(
        self, parameter_id: str | ParameterIndex
    ) -> Optional[DateTimeRange]:
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
        >>> spz.cdpp3dview.parameter_range("Pioneer10")
        <DateTimeRange: 1972-03-05T12:00:00+00:00 -> 2049-12-31T00:00:00+00:00>

        """
        return self._parameter_range(parameter_id)

    def _get_bodies(self):
        URL = f"{self.BASE_URL}/get_bodies"

        with http.urlopen(URL, headers={"Accept": "application/json"}) as response:
            data = response.json()

        return data["bodies"]
