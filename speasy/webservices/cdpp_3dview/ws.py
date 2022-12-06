import zeep
from astropy.io import votable
from typing import List, Dict
from ...config import cdpp_3dview as _cfg
from ...core.cache import CacheCall


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


class _WS_impl:
    def __init__(self, wsdl: str = None):
        wsdl = wsdl or _cfg.wsld_url()
        self._client = zeep.Client(wsdl=wsdl)

    @CacheCall(cache_retention=_cfg.cache_retention())
    def _get_bodies(self, body_type) -> List[Body]:
        bodies = self._client.service.listBodies(pType=body_type)
        return list(map(lambda b: Body(**b.__dict__["__values__"]), bodies))

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
