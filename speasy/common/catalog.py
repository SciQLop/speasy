from .datetime_range import DateTimeRange
from datetime import datetime
from typing import List
from ..common import listify


def _all_are_events(event_list):
    return all(map(lambda e: type(e) == Event, event_list))


class Event(DateTimeRange):
    __slots__ = ['meta']

    def __init__(self, start_time: datetime, stop_time: datetime, meta=None):
        self.meta = meta or {}
        super().__init__(start_time, stop_time)

    def __repr__(self):
        return f"<Event: {self.start_time.isoformat()} -> {self.stop_time.isoformat()} | {self.meta}>"


class Catalog:
    __slots__ = ['_events', 'name', 'meta']

    def __init__(self, name: str, meta: dict = None, events: List[Event] = None):
        self.name = name
        self.meta = meta or {}
        self._events = []
        if events:
            self.append(events)

    def __getitem__(self, index):
        return self._events[index]

    def __len__(self):
        return len(self._events)

    def append(self, events: Event or List[Event]):
        events = listify(events)
        if not _all_are_events(events):
            raise TypeError(
                f"You must provide a {Event} or a List of {Event} instead of {type(events)}")
        self._events += events

    def __iadd__(self, other: Event or List[Event]):
        self.append(other)
        return self

    def pop(self, index=-1):
        return self._events.pop(index)
