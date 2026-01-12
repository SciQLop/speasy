# -*- coding: utf-8 -*-

"""Cdpp 3dView package for Space Physics WebServices Client."""

__author__ = """Richard Hitier"""
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import json
import logging
from typing import Dict
from ...core.http import urlopen

from speasy.core.dataprovider import DataProvider
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex

log = logging.getLogger(__name__)


def body_to_paramindex(body: Dict) -> ParameterIndex:
    """ Build a ParameterIndex from a body dictionary.

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
    """ Build a ParameterIndex from a frame dictionary.

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
    node = ParameterIndex(name=name, provider="ssc", uid=frame["Id"],
                          meta=frame)
    return node


class Cdpp3dViewWebservice(DataProvider):
    """ Cdpp3dViewWebservice Class

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
            data = json.load(response)

        return data
