# -*- coding: utf-8 -*-

"""CDPP_3DView_Webservice package for Speasy."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import logging
from typing import List, Dict

from speasy.core.dataprovider import (GET_DATA_ALLOWED_KWARGS, DataProvider,
                                      ParameterRangeCheck)
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex

from .ws import _WS_impl, Body

log = logging.getLogger(__name__)


def _to_indexes(provider_name: str, bodies: List[Body]) -> Dict[str, ParameterIndex]:
    return {
        b.name: ParameterIndex(name=b.name, provider=provider_name, uid=str(b.naif_id), meta={
            "body_type": str(b.body_type),
            "coverage": str(b.coverage),
            "model_id": str(b.model_id),
            "naif_id": str(b.naif_id),
            "preferred_center": str(b.preferred_center),
            "preferred_frame": str(b.preferred_frame),
            "preferred_star_subset": str(b.preferred_star_subset)
        }) for b in bodies
    }


class CDPP_3DView_Webservice(DataProvider):
    def __init__(self):
        self._impl = _WS_impl()
        DataProvider.__init__(self, provider_name='3DView', provider_alt_names=['CDPP_3DView'])

    def build_inventory(self, root: SpeasyIndex):
        root.Asteroids = SpeasyIndex(name='Asteroids', provider=self.provider_name, uid='Asteroids',
                                     meta=_to_indexes(self.provider_name, self._impl.get_asteroid_list()))
        root.Comets = SpeasyIndex(name='Comets', provider=self.provider_name, uid='Comets',
                                  meta=_to_indexes(self.provider_name, self._impl.get_comet_list()))
        root.Planets = SpeasyIndex(name='Planets', provider=self.provider_name, uid='Planets',
                                   meta=_to_indexes(self.provider_name, self._impl.get_planet_list()))
        root.Satellites = SpeasyIndex(name='Satellites', provider=self.provider_name, uid='Satellites',
                                      meta=_to_indexes(self.provider_name, self._impl.get_satellite_list()))
        root.Spacecrafts = SpeasyIndex(name='Spacecrafts', provider=self.provider_name, uid='Spacecrafts',
                                       meta=_to_indexes(self.provider_name, self._impl.get_spacecraft_list()))
        return root
