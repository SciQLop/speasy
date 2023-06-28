"""AMDA_Webservice utility functions. This module defines some conversion functions specific to AMDA_Webservice, mainly
conversion procedures for parsing CSV and VOTable data.

"""
import datetime
import logging
import os
import re
import tempfile
from typing import Dict, List

import numpy as np
import pandas as pds
from speasy.config import amda as amda_cfg
from speasy.core import epoch_to_datetime64
from speasy.core.any_files import any_loc_open
from speasy.core.datetime_range import DateTimeRange
from speasy.products.catalog import Catalog, Event
from speasy.products.timetable import TimeTable
from speasy.products.variable import (DataContainer, SpeasyVariable,
                                      VariableAxis, VariableTimeAxis)

log = logging.getLogger(__name__)

DATA_CHUNK_SIZE = 10485760

_parameters_header_blocks_regex = re.compile(
    f"(# *PARAMETER_ID : ([^{os.linesep}]+){os.linesep}(# *[A-Z_]+ : [^{os.linesep}]+{os.linesep})+)+")


def _parse_header(fd, expected_parameter: str):
    line = fd.readline().decode()
    header = ""
    meta = {}
    while len(line) and line[0] == '#':
        header += line
        if ':' in line:
            key, value = [v.strip() for v in line[1:].split(':', 1)]
            if key not in meta:
                meta[key] = value
        line = fd.readline().decode()
    parameters_header_blocks = _parameters_header_blocks_regex.findall(header)
    for block in parameters_header_blocks:
        if block[1] == expected_parameter:
            for line in block[0].split('\n'):
                if ':' in line:
                    key, value = [v.strip() for v in line[1:].split(':', 1)]
                    meta[key] = value
            break
    return meta


def load_csv(filename: str, expected_parameter: str) -> SpeasyVariable:
    """Load a CSV file

    Parameters
    ----------
    filename: str
        CSV filename

    Returns
    -------
    SpeasyVariable
        CSV contents
    """
    with any_loc_open(filename, mode='rb') as csv:
        with tempfile.TemporaryFile() as fd:
            # _copy_data(csv, fd)
            fd.write(csv.read())
            fd.seek(0)
            line = fd.readline().decode()
            meta = {}
            y = None
            y_label = None
            meta = _parse_header(fd, expected_parameter)
            columns = [col.strip()
                       for col in meta.get('DATA_COLUMNS', "").split(', ')[:]]
            meta["UNITS"] = meta.get("PARAMETER_UNITS")
            fd.seek(0)
            data = pds.read_csv(fd, comment='#', delim_whitespace=True,
                                header=None, names=columns).values.transpose()
            time, data = epoch_to_datetime64(data[0]), data[1:].transpose()

        if "PARAMETER_TABLE_MIN_VALUES[1]" in meta:
            min_v = np.array(
                [float(v) for v in meta["PARAMETER_TABLE_MIN_VALUES[1]"].split(',')])
            max_v = np.array(
                [float(v) for v in meta["PARAMETER_TABLE_MAX_VALUES[1]"].split(',')])
            y_label = meta["PARAMETER_TABLE[1]"]
            y = (max_v + min_v) / 2.
        elif "PARAMETER_TABLE_MIN_VALUES[0]" in meta:
            min_v = np.array(
                [float(v) for v in meta["PARAMETER_TABLE_MIN_VALUES[0]"].split(',')])
            max_v = np.array(
                [float(v) for v in meta["PARAMETER_TABLE_MAX_VALUES[0]"].split(',')])
            y = (max_v + min_v) / 2.
            y_label = meta["PARAMETER_TABLE[0]"]
        time_axis = VariableTimeAxis(values=time)
        if y is None:
            axes = [time_axis]
        else:
            axes = [time_axis, VariableAxis(
                name=y_label, values=y, is_time_dependent=False)]
        return SpeasyVariable(
            axes=axes,
            values=DataContainer(values=data, meta=meta),
            columns=columns[1:])


def _build_event(data, colnames: List[str]) -> Event:
    return Event(datetime.datetime.strptime(data[0], "%Y-%m-%dT%H:%M:%S.%f"),
                 datetime.datetime.strptime(data[1], "%Y-%m-%dT%H:%M:%S.%f"),
                 {name: value for name, value in zip(colnames[2:], data[2:])})


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
        name = next(filter(lambda e: 'Name' in e,
                           votable.description.split(';\n'))).split(':')[-1]
        # convert astropy votable structure to SpeasyVariable
        tab = votable.get_first_table()
        # prepare data
        data = tab.array.tolist()
        dt_ranges = [DateTimeRange(datetime.datetime.strptime(t0, "%Y-%m-%dT%H:%M:%S.%f"),
                                   datetime.datetime.strptime(t1, "%Y-%m-%dT%H:%M:%S.%f")) for (t0, t1) in
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
        colnames = list(map(lambda f: f.name, tab.fields))
        data = tab.array.tolist()
        events = [_build_event(line, colnames) for line in data]
        var = Catalog(name=name, meta={}, events=events)
        return var


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs) -> Dict:
    """Get parameter arguments

    Parameters
    ----------
    start_time: datetime
        parameter start time
    stop_time: datetime
        parameter stop time
    product: str
        product ID (xmlid)

    Returns
    -------
    dict
        parameter arguments in dictionary
    """
    return {'path': f"amda/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}',
            'output_format': kwargs.get('output_format', amda_cfg.output_format.get())}
