"""AMDA_Webservice utility functions. This module defines some conversion functions specific to AMDA_Webservice, mainly
conversion procedures for parsing CSV and VOTable data.

"""
import datetime
import logging
import os
from typing import List

from speasy.core.any_files import any_loc_open
from speasy.core.datetime_range import DateTimeRange
from speasy.products.catalog import Catalog, Event
from speasy.products.timetable import TimeTable


log = logging.getLogger(__name__)

tt_catalog_time_format = "%Y-%m-%dT%H:%M:%S.%f"


def _build_event(data, col_names: List[str]) -> Event:
    return Event(datetime.datetime.strptime(data[0], tt_catalog_time_format),
                 datetime.datetime.strptime(data[1], tt_catalog_time_format),
                 {name: value for name, value in zip(col_names[2:], data[2:])})


def load_timetable(filename: str) -> TimeTable:
    """Load a timetable file

    Parameters
    ----------
    filename: str
        filename

    Returns
    -------
    TimeTable
        File content loaded as TimeTable
    """
    if '://' not in filename:
        filename = f"file://{os.path.abspath(filename)}"
    with any_loc_open(filename) as votable:
        # save the timetable as a dataframe, speasy.common.SpeasyVariable
        # get header data first

        from astropy.io.votable import parse as parse_votable
        votable = parse_votable(votable)
        if votable.description:
            name = next(filter(lambda e: 'Name' in e,
                               votable.description.split(';\n'))).split(':')[-1]
        else:
            name = os.path.basename(filename)
        # convert astropy votable structure to SpeasyVariable
        tab = votable.get_first_table()
        # prepare data
        data = tab.array.tolist()
        dt_ranges = [DateTimeRange(datetime.datetime.strptime(t0, tt_catalog_time_format),
                                   datetime.datetime.strptime(t1, tt_catalog_time_format)) for (t0, t1) in
                     data]
        var = TimeTable(name=name, meta={}, dt_ranges=dt_ranges)
        return var


def load_catalog(filename: str) -> Catalog:
    """Load a timetable file

    Parameters
    ----------
    filename: str
        filename

    Returns
    -------
    Catalog
        File content loaded as Catalog

    """
    if '://' not in filename:
        filename = f"file://{os.path.abspath(filename)}"
    with any_loc_open(filename) as votable:
        # save the timetable as a dataframe, speasy.common.SpeasyVariable
        # get header data first

        from astropy.io.votable import parse as parse_votable
        votable = parse_votable(votable)
        # convert astropy votable structure to SpeasyVariable
        tab = votable.get_first_table()
        name = next(filter(lambda e: 'Name' in e,
                           votable.description.split(';\n'))).split(':')[-1]
        col_names = list(map(lambda f: f.name, tab.fields))
        data = tab.array.tolist()
        events = [_build_event(line, col_names) for line in data]
        var = Catalog(name=name, meta={}, events=events)
        return var


def is_public(node):
    return node.__dict__.get('is_public', True)


def is_private(node):
    return not is_public(node)
