import os
from pathlib import Path
from typing import List, Optional, Callable
import uuid

import jsonpickle
from ..common.datetime_range import DateTimeRange
import numpy as np
import diskcache as dc
import pandas as pds
from datetime import datetime, timedelta, timezone


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

    @staticmethod
    def _merge_dataframe(df: pds.DataFrame, fragment: pds.DataFrame) -> pds.DataFrame:
        if df is None or len(df) == 0:
            df = fragment
        elif len(fragment):
            if df.index[0] > fragment.index[-1]:
                df = pds.concat([fragment, df])
            else:
                df = pds.concat([df, fragment])
        return df

    def _add_to_cache(self, df: pds.DataFrame, fragments: List[datetime], parameter_id: str, fragment_hours=1):
        if df is not None:
            for fragment in fragments:
                self._data[f"{parameter_id}/{fragment.isoformat()}"] = df[
                    np.logical_and(df.index >= fragment, df.index < fragment + timedelta(hours=fragment_hours))]

    def _get_fragments(self, df: pds.DataFrame, parameter_id: str, fragments: List[datetime],
                       request: Callable[[datetime, datetime], pds.DataFrame], fragment_hours=1) -> pds.DataFrame:
        if len(fragments):
            new_df = request(fragments[0], fragments[-1] + timedelta(hours=fragment_hours))
            df = self._merge_dataframe(df, new_df)
            self._add_to_cache(new_df, fragments, parameter_id, fragment_hours)
        return df

    def get_data(self, parameter_id: str, dt_range: DateTimeRange,
                 request: Callable[[datetime, datetime], pds.DataFrame], fragment_hours=1) -> pds.DataFrame:
        start = datetime(dt_range.start_time.year, dt_range.start_time.month, dt_range.start_time.day,
                         dt_range.start_time.hour, tzinfo=timezone.utc)
        stop = datetime(dt_range.stop_time.year, dt_range.stop_time.month, dt_range.stop_time.day,
                        dt_range.stop_time.hour, tzinfo=timezone.utc) + timedelta(hours=fragment_hours)
        fragments = [start + timedelta(hours=t) for t in range(int((stop - start) / timedelta(hours=fragment_hours)))]
        result = None
        contiguous_fragments = []
        for fragment in fragments:
            key = f"{parameter_id}/{fragment.isoformat()}"
            df = None
            if key in self._data:
                df = self._data[key]
                if df is not None:
                    if len(contiguous_fragments):
                        result = self._get_fragments(result, parameter_id, contiguous_fragments, request,
                                                     fragment_hours)
                        contiguous_fragments = []
                    result = self._merge_dataframe(result, df)
                else:
                    contiguous_fragments.append(fragment)
            else:
                contiguous_fragments.append(fragment)
        if len(contiguous_fragments):
            result = self._get_fragments(result, parameter_id, contiguous_fragments, request, fragment_hours)
        return result[np.logical_and(result.index >= dt_range.start_time, result.index < dt_range.stop_time)]
