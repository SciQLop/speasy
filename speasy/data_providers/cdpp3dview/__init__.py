# -*- coding: utf-8 -*-

"""Cdpp 3dView package for Space Physics WebServices Client."""

__author__ = """Richard Hitier"""
__email__ = "hitier.richard@gmail.com"
__version__ = "0.1.0"

import logging
from typing import Dict, Optional
import json
from urllib.request import urlopen

from speasy.core.dataprovider import DataProvider
from speasy.core.inventory.indexes import SpeasyIndex

log = logging.getLogger(__name__)



class Cdpp3dViewWebservice(DataProvider):
    BASE_URL = "https://3dview.irap.omp.eu/webresources"

    def __init__(self):
        DataProvider.__init__(
            self, provider_name="cdpp3dview", provider_alt_names=["cdpp3d"]
        )

    def build_inventory(self, root: SpeasyIndex):
        # inv = list(map(make_index, self.get_observatories()))
        # root.Trajectories = SpeasyIndex(name='Trajectories', provider='ssc',
        #                                 uid='Trajectories',
        #                                 meta={item.Id: item for item in inv})
        return root

    def version(self, product):
        return 1

    def _get_bodies(self):
        URL = f"{self.BASE_URL}/get_bodies"

        with urlopen(URL) as response:
            data = json.load(response)

        return data["bodies"]

    def _get_frames(self):
        URL = f"{self.BASE_URL}/get_frames"

        with urlopen(URL) as response:
            data = json.load(response)

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
