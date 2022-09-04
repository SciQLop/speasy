from typing import Callable
from speasy.core.datetime_range import DateTimeRange
from datetime import timedelta
from functools import wraps
from speasy.products.variable import merge as var_merge


class SplitLargeRequests(object):
    def __init__(self, threshold: Callable[[], timedelta]):
        self.threshold = threshold

    def __call__(self, get_data: Callable):
        @wraps(get_data)
        def wrapped(wrapped_self, product, start_time, stop_time, **kwargs):
            range = DateTimeRange(start_time, stop_time)
            duration = range.duration
            max_range_per_request = self.threshold()
            if duration <= max_range_per_request:
                return get_data(wrapped_self, product=product, start_time=start_time, stop_time=stop_time, **kwargs)
            else:
                fragments = range.split(max_range_per_request)
                return var_merge(
                    [get_data(wrapped_self, product=product, start_time=r.start_time, stop_time=r.stop_time, **kwargs)
                     for r in fragments])

        return wrapped
