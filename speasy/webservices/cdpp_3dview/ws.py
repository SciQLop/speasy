from copy import copy
from datetime import datetime, timedelta
from functools import lru_cache
from typing import List, Optional

from suds.client import Client

from .trajectory_loader import load_trajectory
from ...config import cdpp_3dview as _cfg
from ...products import SpeasyVariable


class Body:

    def __init__(self, ws_object):
        self._ws_object = ws_object

    def __repr__(self):
        return f"""
++++++++++++++++++++++++++++++++++++++++++++++++
Body: {self.name}
naif_id: {self.naif_id}
model_id: {self.model_id}
body_type: {self.body_type}
size: {self.size}
coverage: {self.coverage}
preferred_frame: {self.preferred_frame}
preferred_center: {self.preferred_center}
preferred_star_subset: {self.preferred_star_subset}
------------------------------------------------
        """

    @property
    def naif_id(self):
        return self._ws_object.naifId

    @property
    def model_id(self):
        return self._ws_object.modelId

    @property
    def name(self):
        return self._ws_object.name

    @property
    def coverage(self):
        return self._ws_object.coverage

    @property
    def body_type(self):
        return self._ws_object.type

    @property
    def size(self):
        return self._ws_object.size

    @property
    def preferred_frame(self):
        return self._ws_object.prefFrame

    @property
    def preferred_center(self):
        return self._ws_object.prefCenter

    @property
    def preferred_star_subset(self):
        return self._ws_object.prefStarSubset

    @property
    def ws_object(self):
        return self._ws_object


class Frame:
    __slots__ = ['_ws_object']

    def __init__(self, ws_object):
        self._ws_object = ws_object

    @property
    def name(self):
        return self._ws_object.name

    @property
    def id(self):
        return self._ws_object.id

    @property
    def description(self):
        return self._ws_object.desc

    @property
    def ws_object(self):
        return self._ws_object

    def __repr__(self):
        return f"""
++++++++++++++++++++++++++++++++++++++++++++++++
Frame: {self.name}
id: {self.id}
------------------------------------------------
        """


def _wrap_first_into_list(list_or_object):
    if type(list_or_object) is list:
        if len(list_or_object):
            return [list_or_object[0]]
        else:
            return []
    return [list_or_object]


def _make_time_vector(start: datetime, stop: datetime) -> List[datetime]:
    start = start.replace(second=0, minute=start.minute)
    stop = stop.replace(second=0, minute=stop.minute + 1)
    assert start <= stop
    return [start + timedelta(minutes=m) for m in range(0, int((stop - start).total_seconds() / 60), 1)]


class _WS_impl:
    def __init__(self, wsdl: str = None):
        wsdl = wsdl or _cfg.wsld_url()
        self._client = Client(wsdl)
        self._frames = self.get_frame_list()

    @lru_cache
    def _get_bodies(self, body_type) -> List[Body]:
        return list(map(Body, self._client.service.listBodies(pType=body_type)))

    def get_spacecraft_list(self) -> List[Body]:
        return self._get_bodies(body_type="SPACECRAFT")

    def get_planet_list(self) -> List[Body]:
        return self._get_bodies(body_type="PLANET")

    def get_satellite_list(self) -> List[Body]:
        return self._get_bodies(body_type="SATELLITE")

    def get_comet_list(self) -> List[Body]:
        return self._get_bodies(body_type="COMET")

    def get_asteroid_list(self) -> List[Body]:
        return self._get_bodies(body_type="ASTEROID")

    @lru_cache
    def get_frame_list(self) -> List[Frame]:
        return list(map(Frame, self._client.service.listFrames2()))

    def get_orbit_data(self, body: Body, start_time: datetime, stop_time: datetime, frame: Optional[Frame] = None,
                       time_vector: Optional[List[datetime]] = None, center: Optional[Body] = None) -> Optional[
        SpeasyVariable]:
        frame = frame or self._frames[int(body.preferred_frame)]
        if center:
            frame = self.frame_with_different_center(frame, center)
        time_vector = time_vector if time_vector is not None else _make_time_vector(start_time, stop_time)
        kernels = self._client.service.listFiles(
            pBodyId=body.naif_id,
            pStartTime=start_time,
            pStopTime=stop_time
        )
        resp = self._client.service.listOrbData2(
            pBodyId=body.naif_id,
            pFrame=frame.ws_object,
            pCenterId=frame.ws_object.center[0].naifId,
            pTimes=time_vector,
            pTimeFiles=_wrap_first_into_list(kernels),
        )
        print(resp)
        if len(resp) == 1:
            return load_trajectory(f"{self._client.wsdl.url.rsplit('/', 1)[0]}{resp[0]}")
        return None

    def frame_with_different_center(self, frame: Frame, new_center: Body) -> Frame:
        new_frame = self._client.factory.create('ns1:Frame')
        new_frame.id = copy(frame.ws_object.id)
        new_frame.name = copy(frame.ws_object.name)
        new_frame.desc = copy(frame.ws_object.desc)
        new_frame.center.append(new_center.ws_object)
        return Frame(new_frame)
