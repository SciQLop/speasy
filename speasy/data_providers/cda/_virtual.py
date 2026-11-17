"""CDAWeb virtual variables computed from the data files, for the CDAWeb functions simple enough to redo here.

CDAWeb only computes them in its web service: the files hold them with no records, so do the variables using
them as axes. Writing them into the file before the ISTP loader reads it serves both from files.
"""
from datetime import timedelta
from typing import Optional

import numpy as np
import pycdfpp

from speasy.core.cache import CacheCall
from speasy.core.codecs import get_codec
from speasy.core.inventory.indexes import DatasetIndex
from speasy.products import SpeasyVariable

from ._patches.reader import _load


def _attribute(variable: pycdfpp.Variable, name: str):
    return variable.attributes[name].value


def _arr_slice(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> np.ndarray:
    # ARR_DIM counts the dimensions of one record, hence the +1, see arr_slice in
    # https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/source/virtual_funcs.pro
    return np.take(cdf[_attribute(virtual, 'COMPONENT_0')].values, int(_attribute(virtual, 'ARR_INDEX')[0]),
                   axis=int(_attribute(virtual, 'ARR_DIM')[0]) + 1)


FUNCTIONS = {'arr_slice': _arr_slice}


def _function_name(variable: pycdfpp.Variable) -> Optional[str]:
    return _attribute(variable, 'FUNCT').lower() if 'FUNCT' in variable.attributes else None


def _is_computable(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> bool:
    return _function_name(virtual) in FUNCTIONS and _attribute(virtual, 'COMPONENT_0') in cdf


def _set_values(cdf: pycdfpp.CDF, name: str, values: np.ndarray) -> None:
    # replaced rather than set_values(): files declare the empty placeholder with any shape, even none at all
    if name in cdf:
        cdf._remove_variable(name)
    cdf.add_variable(name, values=values)


def with_virtuals(cdf: pycdfpp.CDF, master: pycdfpp.CDF) -> pycdfpp.CDF:
    """`cdf` with the values of every virtual variable of `master` it holds what to compute from."""
    for name, virtual in master.items():
        if _is_computable(cdf, virtual):
            _set_values(cdf, name, FUNCTIONS[_function_name(virtual)](cdf, virtual))
    return cdf


def has_computable_virtuals(dataset: DatasetIndex) -> bool:
    return any(getattr(p, 'FUNCT', '').lower() in FUNCTIONS for p in dataset.__dict__.values())


@CacheCall(cache_retention=timedelta(hours=12), is_pure=True)
def read_with_virtuals(url: Optional[str], variable: str, master_cdf_url: str) -> Optional[SpeasyVariable]:
    if url is None:
        return None
    cdf = with_virtuals(_load(url), _load(master_cdf_url))
    loaded = get_codec('application/x-cdf').load_variables(variables=[variable], file=memoryview(pycdfpp.save(cdf)),
                                                           master_cdf_url=master_cdf_url)
    return loaded and loaded.get(variable)
