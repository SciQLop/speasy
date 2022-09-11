""" catalog module
"""

from speasy.core.datetime_range import DateTimeRange
from .base_product import SpeasyProduct
from datetime import datetime
from typing import List
from speasy.core import all_of_type, listify
import pandas as pds


def _all_are_events(event_list):
    return all_of_type(event_list, Event)


class Event(DateTimeRange):
    """The Event class is a DatetimeRange with some meta data. It is supposed to be used with Catalog

    Attributes
    ----------
    start_time : datetime.datetime
    stop_time : datetime.datetime
    meta : dict
            Additional event data

    Methods
    -------

    Notes
    -----
    This class support the same operations as a speasy.common.datetime_range.DateTimeRange.

    See Also
    --------
    speasy.products.catalog.Catalog
    speasy.core.datetime_range.DateTimeRange
    """
    __slots__ = ['meta']

    def __init__(self, start_time: datetime, stop_time: datetime, meta=None):
        self.meta = meta or {}
        super().__init__(start_time, stop_time)

    def __eq__(self, other):
        return (self.meta == other.meta) and super().__eq__(other)

    def __repr__(self):
        return f"<Event: {self.start_time.isoformat()} -> {self.stop_time.isoformat()} | {self.meta}>"


class Catalog(SpeasyProduct):
    """The Catalog class allows to manipulate a goup of events like a simple Python list of Event plus some meta data.

    Attributes
    ----------
    name : str
        Catalog name
    meta : dict
        All additional Catalog meta data

    Methods
    -------
    append:
        Append an Event or a list of Event to the end of the Catalog
    pop:
        Remove and return Event at index (default last)

    Examples
    --------

    >>> import speasy
    >>> from speasy.products import Catalog, Event
    >>> my_catalog = Catalog(name='MyCatalog', meta={'tags':['demo', 'docstrings']}, events=[])
    >>> my_catalog.append(Event('2018-01-01', '2018-01-02', meta={'name':'My first event!'}))
    >>> my_catalog += Event('2019-01-01', '2019-01-02', meta={'name':'My second event!'})
    >>> for e in my_catalog:
    ...     print(e)
    ...
    <Event: 2018-01-01T00:00:00+00:00 -> 2018-01-02T00:00:00+00:00 | {'name': 'My first event!'}>
    <Event: 2019-01-01T00:00:00+00:00 -> 2019-01-02T00:00:00+00:00 | {'name': 'My second event!'}>

    See Also
    --------
    speasy.products.catalog.Event
    speasy.products.timetable.TimeTable
    """
    __slots__ = ['_events', 'name', 'meta']

    def __init__(self, name: str, meta: dict = None, events: List[Event] = None):
        super().__init__()
        self.name = name
        self.meta = meta or {}
        self._events = []
        if events:
            self.append(events)

    def __getitem__(self, index) -> Event:
        return self._events[index]

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return self._events.__iter__()

    def append(self, events: Event or List[Event]) -> None:
        """Append an Event or a list of Event to the end of the Catalog.

        Parameters
        ----------
        events : Event or List[Event]

        Raises
        ------
        TypeError
            If events is neither an Event or a list of Event

        See Also
        --------
        Catalog.pop
        """
        events = listify(events)
        if not _all_are_events(events):
            raise TypeError(
                f"You must provide a {Event} or a List of {Event} instead of {type(events)}")
        self._events += events

    def __iadd__(self, other: Event or List[Event]):
        self.append(other)
        return self

    def pop(self, index: int = -1) -> Event:
        """Remove and return Event at index (default last).

        Parameters
        ----------
        index : int

        Returns
        -------
        Event
            The removed event

        Raises
        ------
        IndexError
            if list is empty or index is out of range.

        """
        return self._events.pop(index)

    def to_dataframe(self) -> pds.DataFrame:
        columns = set()
        data = []
        for e in self:
            columns.update(e.meta.keys())
        columns = list(columns)
        for e in self:
            row = [e.start_time, e.stop_time] + [e.meta.get(column, None) for column in columns]
            data.append(row)
        columns = ['start_time', 'stop_time'] + columns
        return pds.DataFrame(columns=columns, data=data)

    def __repr__(self) -> str:
        return f"""<Catalog: {self.name}>"""
