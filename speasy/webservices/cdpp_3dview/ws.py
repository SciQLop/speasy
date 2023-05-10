from datetime import datetime, timedelta
from functools import lru_cache
from typing import List, Optional

from suds.client import Client

from .trajectory_loader import load_trajectory
from ...config import cdpp_3dview as _cfg
from ...products import SpeasyVariable


class Body:
    __slots__ = ['_naif_id', '_model_id', '_name', '_coverage', '_body_type', '_size', '_preferred_frame',
                 '_preferred_center', '_preferred_star_subset']

    def __init__(self, **kwargs):
        self._naif_id = kwargs['naifId']
        self._model_id = kwargs['modelId']
        self._name = kwargs['name']
        self._coverage = kwargs['coverage']
        self._body_type = kwargs['type']
        self._size = kwargs['size']
        self._preferred_frame = kwargs['prefFrame']
        self._preferred_center = kwargs['prefCenter']
        self._preferred_star_subset = kwargs['prefStarSubset']

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
        return self._naif_id

    @property
    def model_id(self):
        return self._model_id

    @property
    def name(self):
        return self._name

    @property
    def coverage(self):
        return self._coverage

    @property
    def body_type(self):
        return self._body_type

    @property
    def size(self):
        return self._size

    @property
    def preferred_frame(self):
        return self._preferred_frame

    @property
    def preferred_center(self):
        return self._preferred_center

    @property
    def preferred_star_subset(self):
        return self._preferred_star_subset


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
        return list(map(lambda b: Body(**b.__dict__), self._client.service.listBodies(pType=body_type)))

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

    def get_orbit_data(self, body: Body, start_time: datetime, stop_time: datetime, frame: Optional[Frame] = None) -> \
        Optional[SpeasyVariable]:
        if frame is None:
            frame = self._frames[int(body.preferred_frame)]
        kernels = self._client.service.listFiles(
            pBodyId=body.naif_id,
            pStartTime=start_time,
            pStopTime=stop_time
        )
        resp = self._client.service.listOrbData2(
            pBodyId=body.naif_id,
            pFrame=frame.ws_object,
            pCenterId=frame.ws_object.center[0].naifId,
            pTimes=_make_time_vector(start_time, stop_time),
            pTimeFiles=_wrap_first_into_list(kernels),
        )
        print(resp)
        if len(resp) == 1:
            return load_trajectory(f"{self._client.wsdl.url.rsplit('/', 1)[0]}{resp[0]}")
        return None
