from datetime import datetime, timedelta
from copy import copy


class DateTimeRange:
    start_time: datetime
    stop_time: datetime

    __slots__ = ['start_time', 'stop_time']

    def __init__(self, start_time: datetime, stop_time: datetime):
        self.start_time = start_time
        self.stop_time = stop_time

    def __eq__(self, other):
        assert type(other) is DateTimeRange
        return (self.start_time == other.start_time) and (self.stop_time == other.stop_time)

    def intersect(self, other):
        return ((self.stop_time >= other[0]) and (self.start_time <= other[1])) or (
            other[0] <= self.start_time <= other[1]) or (other[0] <= self.stop_time <= other[1])

    def __repr__(self):
        return str(self.start_time.isoformat() + "->" + self.stop_time.isoformat())

    def __getitem__(self, item):
        return self.start_time if item == 0 else self.stop_time

    def __contains__(self, item: object) -> bool:
        if item[0] > item[1]:
            raise ValueError("Negative time range")
        return (self.start_time <= item[0] <= self.stop_time) or \
               (self.start_time <= item[1] <= self.stop_time)

    def __add__(self, other):
        if type(other) is timedelta:
            return DateTimeRange(self.start_time + other, self.stop_time + other)
        else:
            raise TypeError()

    def __sub__(self, other):
        if type(other) is timedelta:
            return DateTimeRange(self.start_time - other, self.stop_time - other)
        elif hasattr(other, 'start_time') and hasattr(other, 'stop_time'):
            res = []
            if not self.intersect(other):
                res = [DateTimeRange(self.start_time, self.stop_time)]
            else:
                if self.start_time < other[0]:
                    res.append(DateTimeRange(self.start_time, other[0]))
                if self.stop_time > other[1]:
                    res.append(DateTimeRange(other[1], self.stop_time))
            return res
        elif type(other) is list:
            diff = []
            if len(other) > 1:
                other.sort()
                left = (DateTimeRange(self.start_time, other[0].stop_time) - other[0])
                if left:
                    diff += left
                diff += [
                    DateTimeRange(pair[0].stop_time, pair[1].start_time)
                    for pair in zip(other[0:-1], other[1:]) if pair[0].stop_time != pair[1].start_time
                ]
                right = (DateTimeRange(other[-1].start_time, self.stop_time) - other[-1])
                if right:
                    diff += right
            elif len(other):
                diff += (self - other[0])
            else:
                return [self]
            return diff
        else:
            raise TypeError()

    def __mul__(self, other):
        if type(other) is float:
            result = copy(self)
            if other >= 1.:
                margins = (result.stop_time - result.start_time) * (other - 1.) / 2.
                result.start_time -= margins
                result.stop_time += margins
            else:
                margins = (result.stop_time - result.start_time) * other / 2.
                result.start_time += margins
                result.stop_time -= margins
            return result
        else:
            raise TypeError()

    def __lt__(self, other):
        return self.start_time < other.start_time

    def __gt__(self, other):
        return self.start_time > other.start_time
