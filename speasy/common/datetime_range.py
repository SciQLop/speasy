from datetime import datetime, timedelta
from . import span_utils


class DateTimeRange:
    start_time: datetime
    stop_time: datetime

    __slots__ = ['start_time', 'stop_time']

    def __init__(self, start_time: datetime, stop_time: datetime):
        self.start_time = start_time
        self.stop_time = stop_time

    def __eq__(self, other):
        return span_utils.equals(self, other)

    def intersect(self, other):
        return span_utils.intersects(self, other)

    def __repr__(self):
        return str(self.start_time.isoformat() + "->" + self.stop_time.isoformat())

    def __getitem__(self, item):
        return self.start_time if item == 0 else self.stop_time

    def __setitem__(self, key, value):
        if key == 0:
            self.start_time = value
        else:
            self.stop_time = value

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
