# -*- coding: utf-8 -*-

"""Cdpp 3dView package for Space Physics WebServices Client."""

__author__ = """Richard Hitier"""
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import json
import logging
from typing import Dict, Optional, Tuple

import numpy as np
from speasy import SpeasyVariable

from speasy.core.data_containers import DataContainer, VariableTimeAxis
from speasy.core.dataprovider import DataProvider
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex

from ...core.http import urlopen

log = logging.getLogger(__name__)


def body_to_paramindex(body: Dict) -> ParameterIndex:
    """Build a ParameterIndex from a body dictionary.

    Parameters
    ----------
    body : Dict
        A body from the cddp 3dview webservice.

    Returns
    -------
    ParameterIndex
        the corresponding ParameterIndex.
    """
    name = body.pop("name")
    body["Id"] = body.pop("id")
    coverage = body.pop("coverage")
    body["start_date"] = coverage[0]
    body["stop_date"] = coverage[1]
    node = ParameterIndex(name=name, provider="ssc", uid=body["Id"], meta=body)
    return node


def frame_to_paramindex(frame: Dict) -> SpeasyIndex:
    """Build a ParameterIndex from a frame dictionary.

    Parameters
    ----------
    frame : Dict
        A frame from the cddp 3dview webservice.

    Returns
    -------
    SpeasyIndex
        the corresponding SpeasyIndex.
    """
    name = frame.pop("name")
    frame["Id"] = frame.pop("id")
    frame["Desc"] = frame.pop("desc")
    frame["Center"] = frame.pop("center")
    node = ParameterIndex(name=name, provider="ssc",
                          uid=frame["Id"], meta=frame)
    return node


def parse_trajectory_json(json_data: str) -> Tuple[np.ndarray, np.ndarray]:
    data = json.loads(json_data)

    entries = data['values']

    time_axis = np.array([np.datetime64(entry['time'][:-1], 'ns') 
                          for entry in entries])

    positions = np.array([entry['position'] for entry in entries])
    speeds = np.array([entry['speed'] for entry in entries])
    values = np.concatenate([positions, speeds], axis=1)

    return time_axis, values


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

    def get_data(self, body: str, frame: str, start: str, stop: str,
                 sampling: int = 3600,
                 format: str = "json") -> Optional[SpeasyVariable]:
        time_axis, values = self._get_trajectory(body, frame, start, stop,
                                                 sampling, format)
        try:
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

    def build_inventory(self, root: SpeasyIndex):
        bodies_index = list(map(body_to_paramindex, self._get_bodies()))
        root.Bodies = SpeasyIndex(
            name="Bodies",
            provider="ssc",
            uid="Bodies",
            meta={item.Id: item for item in bodies_index},
        )
        frames_index = list(map(frame_to_paramindex, self._get_frames()))
        root.Frames = SpeasyIndex(
            name="Frames",
            provider="ssc",
            uid="Frames",
            meta={item.Id: item for item in frames_index},
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
