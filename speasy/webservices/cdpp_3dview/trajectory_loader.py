from typing import Optional, Collection

import numpy as np
from astropy.io import votable

from speasy.core.http import urlopen_with_retry
from ...products import SpeasyVariable, VariableTimeAxis, DataContainer


def _to_datetime(dt: str) -> np.datetime64:
    return np.datetime64(dt, 'ns')


def _to_datetime_array(time_vec: Collection[str]) -> np.ndarray:
    return np.array(list(map(_to_datetime, time_vec)))


def load_trajectory(path: str) -> Optional[SpeasyVariable]:
    with urlopen_with_retry(path) as f:
        import io
        traj = votable.parse_single_table(io.BytesIO(f.read())).to_table()
        if traj and len(traj):
            arr = np.empty((len(traj), 3))
            arr[:, 0] = traj['col2']
            arr[:, 1] = traj['col3']
            arr[:, 2] = traj['col4']
            return SpeasyVariable(axes=[VariableTimeAxis(values=_to_datetime_array(traj['col1']))],
                                  values=DataContainer(values=arr, meta={'UNITS': 'km'}),
                                  columns=["x", "y", "z"])
    return None
