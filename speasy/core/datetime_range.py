from datetime import datetime, timedelta
from speasy.core import span_utils, make_utc_datetime
import numpy as np


class DateTimeRange:
    __slots__ = ['_rng']

    def __init__(self, start_time: datetime or str or np.float64 or float,
                 stop_time: datetime or str or np.float64 or float):
        self._rng = [make_utc_datetime(start_time), make_utc_datetime(stop_time)]

    @property
    def start_time(self):
        return self._rng[0]

    @start_time.setter
    def start_time(self, start_time: datetime or str or np.float64 or float):
        self._rng[0] = make_utc_datetime(start_time)

    @property
    def stop_time(self):
        return self._rng[1]

    @stop_time.setter
    def stop_time(self, stop_time: datetime or str or np.float64 or float):
        self._rng[1] = make_utc_datetime(stop_time)

    def __eq__(self, other):
        return span_utils.equals(self, other)

    def intersect(self, other):
        return span_utils.intersects(self, other)

    def __repr__(self):
        return f'<DateTimeRange: {self.start_time.isoformat()} -> {self.stop_time.isoformat()}>'

    def __getitem__(self, item):
        return self._rng.__getitem__(item)

    def __setitem__(self, key, value):
        self._rng.__setitem__(key, value)

    def __len__(self):
        return 2

    def __contains__(self, item: object) -> bool:
        return span_utils.contains(self, other=item)

    def __add__(self, other):
        if type(other) is timedelta:
            return span_utils.shift(self, other)
        else:
            raise TypeError()

    def __sub__(self, other):
        if type(other) is timedelta:
            return span_utils.shift(self, -other)
        else:
            return span_utils.difference(self, other)

    def __mul__(self, other):
        return span_utils.zoom(self, factor=other)
