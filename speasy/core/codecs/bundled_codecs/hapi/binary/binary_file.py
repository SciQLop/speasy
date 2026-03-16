from typing import List,  Optional, Dict, Any
import logging

import numpy as np
log = logging.getLogger(__name__)

class HapiBinaryParameter:
    def __init__(self, values: np.ndarray, meta: Dict[str, Any]):
        self._meta = meta
        self._values = values

    @property
    def name(self):
        return self._meta["name"]

    @property
    def meta(self):
        return self._meta

    @property
    def values(self):
        return self._values


class HapiBinaryFile:
    def __init__(self):
        self._parameters: List[HapiBinaryParameter] = []

    def create_parameter(self, values: np.ndarray, meta: Dict[str, Any])->HapiBinaryParameter:
        parameter = HapiBinaryParameter(values, meta)
        self._parameters.append(parameter)
        return parameter

    def add_parameter(self, parameter: HapiBinaryParameter):
        self._parameters.append(parameter)

    @property
    def time_axis(self):
        return self._parameters[0].values

    @property
    def time_axis_meta(self):
        return self._parameters[0].meta

    def get_parameter(self, name: str) -> Optional[HapiBinaryParameter]:
        for par in self._parameters:
            if par.name == name:
                return par
        return None

    @property
    def parameters(self):
        return self._parameters
