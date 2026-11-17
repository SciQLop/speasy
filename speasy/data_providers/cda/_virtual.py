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


def _record_count(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> Optional[int]:
    epoch = _attribute(virtual, 'DEPEND_0') if 'DEPEND_0' in virtual.attributes else ''
    return cdf[epoch].shape[0] if epoch in cdf else None


def _missing_records(variable: pycdfpp.Variable, values: np.ndarray, missing: int) -> Optional[np.ndarray]:
    if variable.sparse_records == pycdfpp.SparseRecords.prev_sparse_records:
        return np.repeat(values[-1:], missing, axis=0)
    if variable.sparse_records == pycdfpp.SparseRecords.pad_sparse_records:
        return np.full((missing,) + values.shape[1:], variable.pad_value[0], dtype=values.dtype)
    return None


def _component_values(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> np.ndarray:
    """The component's values over every record of the epoch, the ones a sparse component did not write included.

    simplify: only records after the last written one are rebuilt, pycdfpp already fills the gaps before it.
    """
    component = cdf[_attribute(virtual, 'COMPONENT_0')]
    values, n_records = component.values, _record_count(cdf, virtual)
    if component.is_nrv or n_records is None or not 0 < values.shape[0] < n_records:
        return values
    tail = _missing_records(component, values, n_records - values.shape[0])
    return values if tail is None else np.concatenate([values, tail])


def _reform(values: np.ndarray) -> np.ndarray:
    # IDL's REFORM drops every size-1 dimension; the record axis is kept, a single record still is one
    return values.reshape(values.shape[:1] + tuple(n for n in values.shape[1:] if n != 1))


def _arr_slice(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> np.ndarray:
    # ARR_DIM counts the dimensions of one record in their declared order, hence the +1 (pycdfpp keeps that order
    # for column-major files too, and gives non record varying variables a record axis of 1), see arr_slice in
    # https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/source/virtual_funcs.pro
    return _reform(np.take(_component_values(cdf, virtual), int(_attribute(virtual, 'ARR_INDEX')[0]),
                           axis=int(_attribute(virtual, 'ARR_DIM')[0]) + 1))


FUNCTIONS = {'arr_slice': _arr_slice}


def _function_name(variable: pycdfpp.Variable) -> Optional[str]:
    return _attribute(variable, 'FUNCT').lower() if 'FUNCT' in variable.attributes else None


def _is_computable(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> bool:
    return _function_name(virtual) in FUNCTIONS and _attribute(virtual, 'COMPONENT_0') in cdf


def _set_values(cdf: pycdfpp.CDF, name: str, values: np.ndarray, is_nrv: bool) -> None:
    # replaced rather than set_values(): files declare the empty placeholder with any shape, even none at all
    if name in cdf:
        cdf._remove_variable(name)
    cdf.add_variable(name, values=values, is_nrv=is_nrv)


def with_virtuals(cdf: pycdfpp.CDF, master: pycdfpp.CDF) -> pycdfpp.CDF:
    """`cdf` with the values of every virtual variable of `master` it holds what to compute from.

    A virtual variable varies with records when its component does.
    """
    for name, virtual in master.items():
        if _is_computable(cdf, virtual):
            _set_values(cdf, name, FUNCTIONS[_function_name(virtual)](cdf, virtual),
                        is_nrv=cdf[_attribute(virtual, 'COMPONENT_0')].is_nrv)
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
