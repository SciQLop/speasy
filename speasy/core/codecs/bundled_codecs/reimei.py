"""REIMEI (INDEX) Level-2 ESA/ISA particle files, as JAXA DARTS serves them.

Format: an ASCII header in ``###`` sections (calibration tables, then ``###FORMAT``), then ``###DATA``: one block
per sweep, a ``yyyymmdd hh:mm:ss.ssss counter`` line followed by 32 lines, one per energy step, of
``total gomi ch00 … ch29`` counts. See https://github.com/SciQLop/speasy/issues/437.
"""
import io
import re
from typing import AnyStr, Dict, List, Mapping

import numpy as np

from speasy.core.codecs import Buffer, CodecInterface, register_codec
from speasy.products import DataContainer, SpeasyVariable, VariableAxis, VariableTimeAxis

from .istp import _resolve_url_type

_STEPS, _COLUMNS, _CHANNELS = 32, 32, 30
_BLOCK = 1 + _STEPS
_INVALID_AZIMUTH = 999.99
_CHANNEL_ROW = re.compile(r"^\d\d\s+(-?[\d.]+)\s+[\d.]+\s*$")
_ENERGY_ROW = re.compile(r"^[0-9a-f]{2}(?:\s+([\d.]+)\s+[\d.]+\s+[\d.]+\s+[\d.]+)?\s*$")


def _text(file: Buffer | str | io.IOBase, cache_remote_files: bool) -> str | None:
    kind, content = _resolve_url_type(file, cache_remote_files=cache_remote_files)
    if content is not None and kind == "file":
        with open(content, "rb") as f:
            content = f.read()
    return None if content is None else content.decode("ascii", errors="replace")


def _not_reimei(missing: str) -> ValueError:
    return ValueError(f"This is not a REIMEI Level-2 ESA/ISA file: no {missing} found")


def _table(header: List[str], heading: str, row: re.Pattern, size: int) -> List[re.Match]:
    start = next((i for i, line in enumerate(header) if line.startswith(heading)), None)
    rows = [] if start is None else [row.match(line.strip()) for line in header[start + 1:start + 1 + size]]
    if len(rows) < size or not all(rows):
        raise _not_reimei(f"table of {size} rows after a line starting with '{heading}'")
    return rows


def _energies(header: List[str]) -> np.ndarray:
    # steps 01 and 11 have no energy: the high voltage is still ramping up there
    rows = _table(header, "Step Energy", _ENERGY_ROW, _STEPS)
    return np.array([float(m.group(1)) if m.group(1) else np.nan for m in rows])


def _azimuths(header: List[str]) -> np.ndarray:
    rows = _table(header, "CH  Az", _CHANNEL_ROW, _CHANNELS)
    azimuths = np.array([float(m.group(1)) for m in rows])
    return np.where(azimuths == _INVALID_AZIMUTH, np.nan, azimuths)


def _times(lines: List[str]) -> np.ndarray:
    return np.array([f"{t[:4]}-{t[4:6]}-{t[6:8]}T{t[9:22]}" for t in lines], dtype="datetime64[ns]")


def _sweeps(data: List[str]) -> tuple[np.ndarray, np.ndarray]:
    """Times and counts of the complete sweeps; a last sweep cut short is dropped."""
    blocks = np.array(data[:len(data) // _BLOCK * _BLOCK]).reshape(-1, _BLOCK)
    counts = np.array(" ".join(blocks[:, 1:].ravel()).split(), dtype=np.int32)
    return _times(blocks[:, 0].tolist()), counts.reshape(len(blocks), _STEPS, _COLUMNS)


def _parse(text: str) -> Dict[str, SpeasyVariable]:
    header, marker, data = text.partition("###DATA")
    if not marker:
        raise _not_reimei("###DATA section")
    header = header.splitlines()
    times, counts = _sweeps([line for line in data.splitlines() if line.strip()])
    energy = VariableAxis(values=_energies(header), name="energy", meta={"UNITS": "eV", "CATDESC": "Energy step"})
    azimuth = VariableAxis(values=_azimuths(header), name="azimuth",
                           meta={"UNITS": "deg", "CATDESC": "Channel azimuth in satellite coordinates"})

    def variable(name: str, values: np.ndarray, axes: List[VariableAxis], description: str) -> SpeasyVariable:
        return SpeasyVariable(axes=[VariableTimeAxis(values=times)] + axes,
                              values=DataContainer(values=values, name=name, is_time_dependent=True,
                                                   meta={"UNITS": "counts", "CATDESC": description}))

    return {"counts": variable("counts", counts[:, :, 2:], [energy, azimuth], "Counts per energy step and channel"),
            "total": variable("total", counts[:, :, 0], [energy], "Total counts per energy step"),
            "gomi": variable("gomi", counts[:, :, 1], [energy], "'gomi' counts per energy step, as the file names them")}


_VARIABLES = ("counts", "total", "gomi")


@register_codec
class ReimeiL2(CodecInterface):
    """Read-only codec for the REIMEI (INDEX) Level-2 ESA and ISA files of JAXA DARTS: counts only."""

    def load_variables(self, variables: List[AnyStr], file: Buffer | str | io.IOBase, cache_remote_files=True,
                       **kwargs) -> Mapping[AnyStr, SpeasyVariable | None] | None:
        text = _text(file, cache_remote_files)
        if text is None:
            return None
        parsed = _parse(text)
        return {name: parsed.get(name) for name in variables}

    def load_variable(self, variable: AnyStr, file: Buffer | str | io.IOBase, cache_remote_files=True,
                      **kwargs) -> SpeasyVariable | None:
        loaded = self.load_variables([variable], file, cache_remote_files)
        return loaded[variable] if loaded is not None else None

    def list_variables(self, file: Buffer | str | io.IOBase) -> List[str]:
        return list(_VARIABLES)

    def save_variables(self, variables: List[SpeasyVariable], file: str | io.IOBase | None = None,
                       **kwargs) -> bool | Buffer:
        raise NotImplementedError("Speasy reads REIMEI Level-2 files but can't write them")

    @property
    def supported_extensions(self) -> List[str]:
        return []   # .L2 is far too generic to claim

    @property
    def supported_mimetypes(self) -> List[str]:
        return []

    @property
    def name(self) -> str:
        return "reimei/l2"
