from typing import List, Callable, Optional

from ..common.datetime_range import DateTimeRange
import numpy as np
import diskcache as dc
import pandas as pds
from ..common.variable import SpwcVariable, from_dataframe
from ..common.variable import merge as merge_variables
from datetime import datetime, timedelta, timezone


class Cache:
    __slots__ = ['cache_file', '_data']

    def __init__(self, cache_path: str = ""):
        self._data = dc.Cache(cache_path, size_limit=int(20e9))
        self._data.check(fix=True)

    def __del__(self):
        pass

    def __contains__(self, item):
        return item in self._data

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    # @staticmethod
    # def _merge_dataframe(df: pds.DataFrame, fragment: pds.DataFrame) -> pds.DataFrame:
    #    if df is None or len(df) == 0:
    #        df = fragment
    #    elif len(fragment):
    #        if df.index[0] > fragment.index[-1]:
    #            df = pds.concat([fragment, df])
    #        else:
    #            df = pds.concat([df, fragment])
    #    return df

    def _add_to_cache(self, var: SpwcVariable, fragments: List[datetime], parameter_id: str, fragment_duration_hours=1):
        if var is not None:
            for fragment in fragments:
                self._data[f"{parameter_id}/{fragment.isoformat()}"] = var[fragment:fragment + timedelta(
                    hours=fragment_duration_hours)]

    def _get_fragments(self, var: SpwcVariable, parameter_id: str, fragments: List[datetime],
                       request: Callable[[datetime, datetime], SpwcVariable], fragment_hours=1) -> SpwcVariable:
        if len(fragments):
            new_var = request(fragments[0], fragments[-1] + timedelta(hours=fragment_hours))
            var = merge_variables([var, new_var])
            self._add_to_cache(new_var, fragments, parameter_id, fragment_hours)
        return var

    def get_data(self, parameter_id: str, dt_range: DateTimeRange,
                 request: Callable[[datetime, datetime], SpwcVariable], fragment_hours=1) -> Optional[SpwcVariable]:

        margins = (dt_range.stop_time - dt_range.start_time) * 0.2
        start = dt_range.start_time - margins
        stop = dt_range.stop_time + margins
        start = datetime(start.year, start.month, start.day, int(start.hour / fragment_hours) * fragment_hours,
                         tzinfo=timezone.utc)
        stop = datetime(stop.year, stop.month, stop.day, stop.hour, tzinfo=timezone.utc) + timedelta(hours=1)
        fragments = []
        tend = start
        while tend < stop:
            fragments.append(tend)
            tend += timedelta(hours=fragment_hours)
        result = None
        contiguous_fragments = []
        for fragment in fragments:
            key = f"{parameter_id}/{fragment.isoformat()}"
            var = None
            if key in self._data:
                var = self._data[key]
                if isinstance(var, pds.DataFrame):  # convert any remaining DataFrame from previous releases
                    var = from_dataframe(var)
                if var is not None:
                    if len(contiguous_fragments):
                        result = self._get_fragments(result, parameter_id, contiguous_fragments, request,
                                                     fragment_hours)
                        contiguous_fragments = []
                    result = merge_variables([result, var])
                else:
                    contiguous_fragments.append(fragment)
            else:
                contiguous_fragments.append(fragment)
        if len(contiguous_fragments):
            result = self._get_fragments(result, parameter_id, contiguous_fragments, request, fragment_hours)
        if result is not None:
            return result[dt_range.start_time:dt_range.stop_time]
        return None
