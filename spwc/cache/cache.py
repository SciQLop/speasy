import os
from pathlib import Path
from typing import List, Optional, Callable
import uuid

import jsonpickle
from ..common.datetime_range import DateTimeRange
import numpy as np
import diskcache as dc
import pandas as pds
from _datetime import datetime, timedelta


class Cache:
    __slots__ = ['cache_file', '_data']

    def __init__(self, cache_path: str = ""):
        self._data = dc.Cache(cache_path)
        self._data.check(fix=True)

    def __del__(self):
        pass

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def get_data(self, parameter_id: str, dt_range: DateTimeRange,
                 requtest: Callable[[datetime, datetime], pds.DataFrame]) -> List[pds.DataFrame]:
        start = datetime(dt_range.start_time.year, dt_range.start_time.month, dt_range.start_time.day,
                         dt_range.start_time.hour)
        stop = datetime(dt_range.stop_time.year, dt_range.stop_time.month, dt_range.stop_time.day,
                        dt_range.stop_time.hour + 1)
        fragments = [start + timedelta(hours=t) for t in range(int((stop - start) / timedelta(hours=1)))]
        result = None
        for fragment in fragments:
            key = f"{parameter_id}/{fragment.isoformat()}"
            if key in self._data:
                df = self._data[key]
            else:
                df = requtest(fragment, fragment + timedelta(hours=1))
                self._data[key] = df
            if result is None:
                result = df
            elif df is not None:
                if result.index[0] > df.index[-1]:
                    result = pds.concat([df, result])
                else:
                    result = pds.concat([result, df])
        return result[np.logical_and(result.index >= dt_range.start_time, result.index < dt_range.stop_time)]
