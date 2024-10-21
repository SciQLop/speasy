from typing import List, AnyStr, Optional, Mapping
import io
from speasy.core.codecs import CodecInterface, register_codec
import numpy as np
import re
import os
import pandas as pds
from speasy.core.any_files import any_loc_open
from speasy.core import epoch_to_datetime64
from speasy.products import SpeasyVariable, VariableAxis, VariableTimeAxis, DataContainer
import tempfile
import logging

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


def _load_csv(filename: str, expected_parameter: str) -> SpeasyVariable:
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


@register_codec
class AmdaCsv(CodecInterface):

    def load_variables(self, variables: List[AnyStr], file: bytes or str or io.IOBase, cache_remote_files=True,
                       **kwargs) -> Mapping[
                                        AnyStr, SpeasyVariable] or None:
        if len(variables) != 1:
            raise ValueError("Only one variable can be loaded at a time")
        return {variables[0]: _load_csv(file, variables[0])}

    def load_variable(self, variable: AnyStr, file: bytes or str or io.IOBase, cache_remote_files=True, **kwargs) ->Optional[SpeasyVariable]:
        return _load_csv(file, variable)

    def save_variables(self, variables: List[SpeasyVariable], file: bytes or str or io.IOBase, **kwargs) -> bool:
        raise NotImplementedError("Saving variables is not supported for this codec")

    @property
    def supported_extensions(self) -> List[str]:
        return []

    @property
    def supported_mimetypes(self) -> List[str]:
        return []

    @property
    def name(self) -> str:
        return "amda/csv"
