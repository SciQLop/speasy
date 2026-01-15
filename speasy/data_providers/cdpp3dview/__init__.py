# -*- coding: utf-8 -*-

"""Cdpp 3dView package for Space Physics WebServices Client."""

__author__ = """Richard Hitier"""
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import logging
from typing import Dict, Optional

from speasy import SpeasyVariable
from speasy.core.algorithms import AllowedKwargs
from speasy.core.cache._providers_caches import CACHE_ALLOWED_KWARGS
from speasy.core.dataprovider import GET_DATA_ALLOWED_KWARGS, DataProvider
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex
from speasy.core.proxy import PROXY_ALLOWED_KWARGS
from speasy.core.typing import AnyDateTimeType

from ...core.http import urlopen
from ._coordinate_frames import _COORDINATE_FRAMES

log = logging.getLogger(__name__)


class Cdpp3dViewWebservice(DataProvider):
    """Cdpp3dViewWebservice Class

    Parameters
    ----------
    DataProvider : speasy.core.dataprovider.DataProvider
        core DataProvider class

    Returns
    -------
    Cdpp3dViewWebservice
        Cdpp3dViewWebservice instance
    """

    BASE_URL = "https://3dview.irap.omp.eu/webresources"

    def __init__(self):
        DataProvider.__init__(
            self, provider_name="cdpp3dview", provider_alt_names=["cdpp3d"]
        )

    # TODO: move to _inventory_builder.build_inventory
    def build_inventory(self, root: SpeasyIndex):
        from speasy.core import fix_name
        from speasy.core.inventory.indexes import make_inventory_node

        # Create root node Trajectories
        trajectory_node = make_inventory_node(
            root,
            SpeasyIndex,
            provider="cdpp3dview",
            uid="Trajectories",
            name="Trajectories",
        )

        # Get datas
        bodies = self._get_bodies()
        frames = self._get_frames()

        # Group bodies by type (Spacecraft, Comet, ...)
        bodies_by_type = {}
        for body in bodies:
            body_type = body.get('type', 'SPACECRAFT')
            if body_type not in bodies_by_type:
                bodies_by_type[body_type] = []
            bodies_by_type[body_type].append(body)

        # Build inventory hierarchy
        for body_type, bodies_list in bodies_by_type.items():
            # Create node <body_type>
            type_node = make_inventory_node(
                trajectory_node,
                SpeasyIndex,
                provider="cdpp3dview",
                uid=body_type,
                name=fix_name(body_type),
                description=f"{body_type} bodies"
            )

            # For each body
            for body in bodies_list:
                body_name = body['name']

                # Create body node
                body_node = make_inventory_node(
                    type_node,
                    ParameterIndex,
                    provider="cdpp3dview",
                    uid=body_name,
                    name=fix_name(body_name),
                    description=f"{body_name} trajectories",
                    start_date=body['coverage'][0],
                    stop_date=body['coverage'][1]
                )
        return root

    # TODO: add decorators
    # @UnversionedProviderCache(prefix="cdpp3dview", fragment_hours=24)
    # @Proxyfiable(GetProduct, get_parameter_args_ws)
    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS
        + CACHE_ALLOWED_KWARGS
        + GET_DATA_ALLOWED_KWARGS
        + ["sampling", "format"]
    )
    # @EnsureUTCDateTime()
    # @ParameterRangeCheck()
    # TODO: change signature
    def get_data(
        self,
        product: str,
        start_time: AnyDateTimeType,
        stop_time: AnyDateTimeType,
        coordinate_frame: str = "J2000",
        **kwargs,
    ) -> Optional[SpeasyVariable]:
        if coordinate_frame not in self._get_frames():
            raise ValueError(
                f"Coordinate frame '{coordinate_frame}' is not available. "
                f"Available frames are: {self._get_frames()}"
            )

        var = self._get_trajectory(
            product=product,
            start=start_time,
            stop=stop_time,
            coordinate_frame=coordinate_frame,
            **kwargs,
        )
        return var

    def version(self, product):
        return 1

    def _get_bodies(self):
        URL = f"{self.BASE_URL}/get_bodies"

        with urlopen(URL, headers={"Accept": "application/json"}) as response:
            data = response.json()

        return data["bodies"]

    def _get_frames(self):
        frames = [f.name for f in _COORDINATE_FRAMES]
        return frames

    # TODO: write accordingly to 3dview REST api
    #       get cdf format
    #       build  and return SpeasyVariable ?
    def _get_trajectory(
        self,
        product: str,
        start: AnyDateTimeType,
        stop: AnyDateTimeType,
        coordinate_frame,
        sampling,
        format,
    ):
        body = self._to_parameter_index(product).spz_name()

        URL = (
            f"{self.BASE_URL}/get_trajectory?"
            f"body={body}&frame={coordinate_frame}&start={start}&stop={stop}"
            f"&sampling={sampling}&format={format}"
        )
        print(URL)

        # Do wahaterver with cdflib to return a SpeasyVariable
        # return var
        return None
