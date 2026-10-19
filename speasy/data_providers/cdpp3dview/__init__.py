# -*- coding: utf-8 -*-

"""Cdpp 3dView package for Space Physics WebServices Client."""

__author__ = """Richard Hitier"""
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import json
import logging
from datetime import datetime
from typing import Callable, List, Optional

import numpy as np

from speasy import SpeasyVariable
from speasy.products.variable import DataContainer, VariableTimeAxis
from speasy.core import fix_name, http
from speasy.core.algorithms import AllowedKwargs
from speasy.core.cache import CACHE_ALLOWED_KWARGS, UnversionedProviderCache

from speasy.core.codecs.codecs_registry import get_codec
from speasy.core.dataprovider import (
    GET_DATA_ALLOWED_KWARGS,
    DataProvider,
    ParameterRangeCheck,
    register_provider,
)
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import (
    ParameterIndex,
    SpeasyIndex,
    make_inventory_node,
)
from speasy.core.proxy import PROXY_ALLOWED_KWARGS, GetProduct, Proxyfiable, Version
from speasy.core.time import EnsureUTCDateTime, make_utc_datetime
from speasy.core.typing import AnyDateTimeType
from email.utils import format_datetime

log = logging.getLogger(__name__)


class Cdpp3dViewWebException(Exception):
    pass


def _make_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    coordinate_frame = kwargs.get('coordinate_frame', 'J2000')
    sampling = kwargs.get('sampling', '600')
    return f"{prefix}/{product}/{coordinate_frame}/{sampling}/{start_time}"


def _resolve_coordinate_frame(coordinate_frame: Optional[str], coordinate_system: Optional[str]) -> str:
    """coordinate_system is an alias for coordinate_frame (SSCWeb calls it coordinate_system;
    3dView's own REST API calls it frame/coordinate_frame). Accept either spelling, but reject
    the two disagreeing rather than silently picking one."""
    if coordinate_frame is not None and coordinate_system is not None and coordinate_frame != coordinate_system:
        raise Cdpp3dViewWebException(
            f"Got conflicting coordinate_frame={coordinate_frame!r} and "
            f"coordinate_system={coordinate_system!r} -- they are aliases for the same thing, pass only one."
        )
    return coordinate_frame or coordinate_system or "J2000"


def _get_json(url: str):
    response = http.get(url, headers={"Accept": "application/json"})
    if response.status_code != 200:
        raise Cdpp3dViewWebException(f"{url} answered HTTP {response.status_code}")
    return response.json()


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"cdpp3dview/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}', 'coordinate_system': kwargs.get('coordinate_frame', 'J2000'),
            'sampling': kwargs.get('sampling', '600')}

CDPP3DVIEW_MIN_PROXY_VERSION = Version('0.14.0')
TRANSFORMS_PREFIX = "Transforms/"
# 3DView publishes no coverage per frame. Measured: every frame fails in 1850 and Earth or planet frames answer
# from 1900 to at least 2500, while small-body frames (67PCG_CSO, ...) answer HTTP 500 outside their ephemerides.
FRAME_COVERAGE = ("1900-01-01T00:00:00Z", "2500-01-01T00:00:00Z")


def _is_transform(product: str) -> bool:
    return product.startswith(TRANSFORMS_PREFIX)


def _load_transform_json(payload: bytes) -> Optional[SpeasyVariable]:
    steps = json.loads(payload)["values"]
    if not steps:
        return None
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=np.array([s["time"].rstrip("Z") for s in steps], dtype="datetime64[ns]"))],
        values=DataContainer(values=np.array([s["matrix"] for s in steps], dtype=np.float64), name="matrix"))


def _tag_trajectory(var: Optional[SpeasyVariable], frame: str) -> Optional[SpeasyVariable]:
    if var is not None:
        var.meta["COORDINATE_SYSTEM"] = frame
    return var


def _tag_transform(var: Optional[SpeasyVariable], source: str, target: str) -> Optional[SpeasyVariable]:
    # Cluster CAA Metadata Dictionary §7.8 convention: v_target = M @ v_source
    if var is not None:
        var.meta.update({"COORDINATE_SYSTEM": source, "TARGET_SYSTEM": target, "TENSOR_ORDER": 2})
    return var

@register_provider
class Cdpp3dViewWebservice(DataProvider):
    NAME = "cdpp3dview"
    ALIASES = ("3DView",)
    BASE_URL = "https://3dview.irap.omp.eu/webresources"

    def __init__(self):
        self._frames: List[str] = []
        DataProvider.__init__(self, min_proxy_version=CDPP3DVIEW_MIN_PROXY_VERSION)
        self._cdf_codec = get_codec('application/x-cdf')

    def version(self, product):  # NOSONAR (S1172)
        return 1

    def _get_frames_descriptions(self):
        return _get_json(f"{self.BASE_URL}/get_frames")['frames']

    def _build_frames_list(self):
        return [f["name"] for f in self._get_frames_descriptions()]

    def _build_transforms_tree(self, root: SpeasyIndex, frames):
        transforms_node = make_inventory_node(root, SpeasyIndex, provider="cdpp3dview", uid="Transforms",
                                              name="Transforms",
                                              description="Rotation matrices from each frame to the frame "
                                                          "given as coordinate_frame")
        for frame in frames:
            make_inventory_node(transforms_node, ParameterIndex, provider="cdpp3dview",
                                uid=f"{TRANSFORMS_PREFIX}{frame['name']}", name=fix_name(frame['name']),
                                description=f"Rotation matrices from {frame['name']} ({frame['desc']})",
                                start_date=FRAME_COVERAGE[0], stop_date=FRAME_COVERAGE[1])

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
        frames = self._get_frames_descriptions()
        self._frames = [f["name"] for f in frames]

        trajectory_node = make_inventory_node(
            root,
            SpeasyIndex,
            provider="cdpp3dview",
            uid="Trajectories",
            name="Trajectories",
        )
        self._build_bodies_tree(trajectory_node)
        self._build_transforms_tree(root, frames)

        return root

    def get_data(
        self,
        product: str,
        start_time: AnyDateTimeType,
        stop_time: AnyDateTimeType,
        coordinate_frame: Optional[str] = None,
        coordinate_system: Optional[str] = None,
        sampling: str = "600",
        if_newer_than: Optional[AnyDateTimeType] = None,
        **kwargs,
    ) -> Optional[SpeasyVariable]:
        coordinate_frame = _resolve_coordinate_frame(coordinate_frame, coordinate_system)
        if isinstance(product, ParameterIndex):
            product = product.spz_uid()
        if _is_transform(product):
            return self._get_data_transform(product, start_time, stop_time, coordinate_frame, sampling,
                                            if_newer_than, **kwargs)
        available_frames = self.get_frames()
        if not available_frames:
            log.warning(
                "No available coordinate frames retrieved from 3dView.")
            coordinate_frame = "J2000"
        elif coordinate_frame not in available_frames:
            exception_msg = (
                f"Coordinate frame '{coordinate_frame}' is not available.\n"
                f"Available frames are: {available_frames}"
            )
            raise Cdpp3dViewWebException(exception_msg)

        var = self._get_trajectory(
            product=product,
            start_time=start_time,
            stop_time=stop_time,
            coordinate_frame=coordinate_frame,
            sampling=sampling,
            if_newer_than=if_newer_than,
            **kwargs,
        )
        return _tag_trajectory(var, coordinate_frame)

    def _get_data_transform(self, product, start_time, stop_time, target_frame, sampling, if_newer_than, **kwargs):
        source_frame = product[len(TRANSFORMS_PREFIX):]
        self._check_frames(source_frame, target_frame)
        var = self._get_transform(product=product, start_time=start_time, stop_time=stop_time,
                                  coordinate_frame=target_frame, sampling=sampling, if_newer_than=if_newer_than,
                                  **kwargs)
        return _tag_transform(var, source_frame, target_frame)

    def _check_frames(self, *frames):
        available_frames = self.get_frames()
        if not available_frames:
            log.warning("No available coordinate frames retrieved from 3dView, sending the request unchecked.")
            return
        for frame in frames:
            if frame not in available_frames:
                raise Cdpp3dViewWebException(
                    f"Coordinate frame '{frame}' is not available.\nAvailable frames are: {available_frames}")

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS
        + CACHE_ALLOWED_KWARGS
        + GET_DATA_ALLOWED_KWARGS
        + ["coordinate_frame", "sampling", "if_newer_than", "format"],
        )
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @UnversionedProviderCache(prefix="cdpp3dview", fragment_hours=lambda x: 24, entry_name=_make_cache_entry_name)
    @Proxyfiable(GetProduct, get_parameter_args, min_version=CDPP3DVIEW_MIN_PROXY_VERSION)
    def _get_trajectory(
        self,
        product: str,
        start_time: AnyDateTimeType,
        stop_time: AnyDateTimeType,
        coordinate_frame: str,
        sampling: str = "600",
        if_newer_than: Optional[AnyDateTimeType] = None,
        format: str = "cdf",
        **kwargs,
    ):
        body = self._to_parameter_index(product).spz_uid()

        date_format = "%Y-%m-%dT%H:%M:%S"
        start_date = start_time.strftime(date_format)
        stop_date = stop_time.strftime(date_format)
        URL = (
            f"{self.BASE_URL}/get_trajectory?"
            f"body={body}&frame={coordinate_frame}&"
            f"start={start_date}&stop={stop_date}&"
            f"sampling={sampling}&format={format}"
        )
        return self._fetch(URL, lambda payload: self._cdf_codec.load_variable(file=payload, variable="pos"),
                           if_newer_than)

    # The proxy can't serve transforms until it runs a speasy that has them, so they skip it.
    @AllowedKwargs(
        CACHE_ALLOWED_KWARGS
        + GET_DATA_ALLOWED_KWARGS
        + PROXY_ALLOWED_KWARGS
        + ["coordinate_frame", "sampling", "if_newer_than"],
        )
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    @UnversionedProviderCache(prefix="cdpp3dview", fragment_hours=lambda x: 24, entry_name=_make_cache_entry_name)
    def _get_transform(
        self,
        product: str,
        start_time: AnyDateTimeType,
        stop_time: AnyDateTimeType,
        coordinate_frame: str,
        sampling: str = "600",
        if_newer_than: Optional[AnyDateTimeType] = None,
        **kwargs,
    ):
        date_format = "%Y-%m-%dT%H:%M:%S"
        URL = (
            f"{self.BASE_URL}/get_transform_matrices?"
            f"fromframe={product[len(TRANSFORMS_PREFIX):]}&toframe={coordinate_frame}&"
            f"start={start_time.strftime(date_format)}&stop={stop_time.strftime(date_format)}&"
            f"sampling={sampling}&format=json"
        )
        # Not format=cdf: its Epoch is 30 days early (2015-10-16 comes back as 2015-09-16), the JSON times are right
        return self._fetch(URL, _load_transform_json, if_newer_than)

    def _fetch(self, URL: str, load: Callable[[bytes], SpeasyVariable], if_newer_than: Optional[AnyDateTimeType]):
        headers = {}
        if if_newer_than is not None:
            # If-Modified-Since must be a valid HTTP-date (RFC 7231), datetime.ctime()
            # is not one and makes the server answer 400
            headers["If-Modified-Since"] = format_datetime(make_utc_datetime(if_newer_than), usegmt=True)
        resp = http.get(URL, headers=headers, timeout=5*60)
        if resp.status_code == 200:
            return load(resp.bytes)
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
        if not self._frames:
            # build_inventory() is the only other place that fills the frames list,
            # and it never runs locally when the inventory is served by the proxy.
            try:
                self._frames = self._build_frames_list()
            except Exception as e:
                log.warning(f"Failed to retrieve coordinate frames from 3dView: {e}")
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
        if isinstance(parameter_id, str) and _is_transform(parameter_id):
            return DateTimeRange(*FRAME_COVERAGE)
        return self._parameter_range(parameter_id)

    def _get_bodies(self):
        return _get_json(f"{self.BASE_URL}/get_bodies")["bodies"]
