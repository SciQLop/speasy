"""AMDA utility functions. This module defines some conversion functions specific to AMDA, mainly
conversion procedures for parsing CSV and VOTable data.

"""
import os
import datetime
from urllib.request import urlopen
from lxml import etree
from speasy.common.variable import SpeasyVariable
import pandas as pds
import numpy as np

def load_csv(filename: str):
    """Load a CSV file

    :param filename: CSV filename
    :type filename: str
    :return: CSV contents
    :rtype: SpeasyVariable
    """
    if '://' not in filename:
        filename = f"file://{os.path.abspath(filename)}"
    with urlopen(filename) as csv:
        line = csv.readline().decode()
        meta = {}
        y = None
        while line[0] == '#':
            if ':' in line:
                key, value = line[1:].split(':', 1)
                meta[key.strip()] = value.strip()
            line = csv.readline().decode()
        columns = [col.strip() for col in meta['DATA_COLUMNS'].split(',')[:]]
        with urlopen(filename) as f:
            data = pds.read_csv(f, comment='#', delim_whitespace=True, header=None, names=columns).values.transpose()
        time, data = data[0], data[1:].transpose()
        if "PARAMETER_TABLE_MIN_VALUES[1]" in meta:
            min_v = np.array([float(v) for v in meta["PARAMETER_TABLE_MIN_VALUES[1]"].split(',')])
            max_v = np.array([float(v) for v in meta["PARAMETER_TABLE_MAX_VALUES[1]"].split(',')])
            y = (max_v + min_v) / 2.
        elif "PARAMETER_TABLE_MIN_VALUES[0]" in meta:
            min_v = np.array([float(v) for v in meta["PARAMETER_TABLE_MIN_VALUES[0]"].split(',')])
            max_v = np.array([float(v) for v in meta["PARAMETER_TABLE_MAX_VALUES[0]"].split(',')])
            y = (max_v + min_v) / 2.
        return SpeasyVariable(time=time, data=data, meta=meta, columns=columns[1:], y=y)

def load_timetable(filename: str):
    """Load a timetable file

    :param filename: filename
    :type filename: str
    :return: SpeasyVariable
    :rtype: ????

    """
    if '://' not in filename:
        filename = f"file://{os.path.abspath(filename)}"
    with urlopen(filename) as votable:
        # save the timetable as a dataframe, speasy.common.SpeasyVariable
        # get header data first
        from astropy.io.votable import parse as parse_votable
        import io
        votable=parse_votable(io.BytesIO(votable.read()))
        # convert astropy votable structure to SpeasyVariable
        tab=votable.resources[0].tables[0]
        import numpy as np
        # prepare data
        data=np.array([[datetime.datetime.strptime(t0, "%Y-%m-%dT%H:%M:%S.%f").timestamp(),\
                datetime.datetime.strptime(t1, "%Y-%m-%dT%H:%M:%S.%f").timestamp()] for (t0,t1) in tab.array], dtype=float)
        var = SpeasyVariable(columns = [f.name for f in tab.fields], data=data, time=data[:,0])
        return var

def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    """Get parameter arguments

    :param start_time: parameter start time
    :type start_time: datetime.datetime
    :param stop_time: parameter stop time
    :type stop_time: datetime.datetime
    :return: parameter arguments in dictionary
    :rtype: dict
    """
    return {'path': f"amda/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}


