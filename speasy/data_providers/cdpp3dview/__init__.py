# -*- coding: utf-8 -*-

"""Cdpp 3dView package for Space Physics WebServices Client."""

__author__ = """Richard Hitier"""
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import logging
from typing import Optional

from speasy import SpeasyVariable
from speasy.core.data_containers import DataContainer, VariableTimeAxis
from speasy.core.dataprovider import DataProvider
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex

from ...core.http import urlopen

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

    # TODO: add decorators
    # @UnversionedProviderCache(prefix="cdpp3dview", fragment_hours=24)
    # @Proxyfiable(GetProduct, get_parameter_args_ws)
    # @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS + ['sampling'])
    # @EnsureUTCDateTime()
    # @ParameterRangeCheck()
    # TODO: change signature
    def get_data(self, body: str, frame: str, start: str, stop: str,
                 sampling: int = 3600,
                 format: str = "json") -> Optional[SpeasyVariable]:
        time_axis, values = self._get_trajectory(body, frame, start, stop,
                                                 sampling, format)
        try:
            # TODO: Maybe should come from _get_trajectory ?
            return SpeasyVariable(
                axes=[VariableTimeAxis(values=time_axis)],
                values=DataContainer(values,
                                     meta={'CoordinateSystem': 'GSE',
                                           'UNITS': 'km, km/s'}),
                columns=['X', 'Y', 'Z', 'Vx', 'Vy', 'Vz']
            )
        except Exception as e:
            log.error(f"Error parsing trajectory: {e}")
        return None

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

    def version(self, product):
        return 1

    def _get_bodies(self):
        URL = f"{self.BASE_URL}/get_bodies"

        with urlopen(URL, headers={"Accept": "application/json"}) as response:
            data = response.json()

        return data["bodies"]

    def _get_frames(self):
        URL = f"{self.BASE_URL}/get_frames"

        with urlopen(URL, headers={"Accept": "application/json"}) as response:
            data = response.json()

        return data["frames"]

    # TODO: write accordingly to 3dview REST api
    #       get cdf format
    #       build  and return SpeasyVariable ?
    def _get_trajectory(self, body, frame, start, stop, sampling=3600,
                        format="json"):
        URL = (
            f"{self.BASE_URL}/get_trajectory?"
            f"body={body}&frame={frame}&start={start}&stop={stop}"
            f"&sampling={sampling}&format={format}"
        )
        with urlopen(URL) as response:
            data = response.json()

        return data
