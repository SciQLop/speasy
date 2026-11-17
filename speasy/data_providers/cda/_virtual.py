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
    component = cdf[_component_name(virtual)]
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


def _flip_vert(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> np.ndarray:
    # IDL's reverse(img[*,*,j]) flips the first dimension of each record, see alternate_view in virtual_funcs.pro
    return _component_values(cdf, virtual)[:, ::-1]


def _makes_vary(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> bool:
    # read_myCDF.pro's MAKE_VARY: a clone the master declares record varying turns an NRV component into a varying one
    return (_function_name(virtual) == 'clone' and not virtual.is_nrv and cdf[_component_name(virtual)].is_nrv
            and _record_count(cdf, virtual) is not None)


def _clone(cdf: pycdfpp.CDF, virtual: pycdfpp.Variable) -> np.ndarray:
    values = _component_values(cdf, virtual)
    return np.repeat(values, _record_count(cdf, virtual), axis=0) if _makes_vary(cdf, virtual) else values


# alternate_view reuses the component's data as is (virtual_funcs.pro), clone reads it (read_myCDF.pro)
FUNCTIONS = {
    'arr_slice': _arr_slice,
    'alternate_view': _component_values,
    'alternate_view_flip_vert': _flip_vert,
    'clone': _clone,
}


def _function_name(variable: pycdfpp.Variable) -> Optional[str]:
    return _attribute(variable, 'FUNCT').lower() if 'FUNCT' in variable.attributes else None


def _component_name(virtual: pycdfpp.Variable) -> str:
    return _attribute(virtual, 'COMPONENT_0')


def _in_dependency_order(master: pycdfpp.CDF) -> list[tuple[str, pycdfpp.Variable]]:
    """The computable virtual variables, each after the virtual variable it is computed from; cycles are dropped."""
    remaining = {name: v for name, v in master.items() if _function_name(v) in FUNCTIONS and 'COMPONENT_0' in v.attributes}
    ordered = []
    while ready := [(name, v) for name, v in remaining.items() if _component_name(v) not in remaining]:
        ordered += ready
        for name, _ in ready:
            del remaining[name]
    return ordered


def _as_declared(values: np.ndarray, virtual: pycdfpp.Variable) -> np.ndarray:
    # CDAWeb writes a virtual variable with the numeric type its master declares (doubles become CDF_REAL4 views)
    declared = virtual.values.dtype
    return values.astype(declared) if values.dtype.kind in 'iuf' and declared.kind in 'iuf' else values


def _set_values(cdf: pycdfpp.CDF, name: str, values: np.ndarray, is_nrv: bool) -> None:
    # replaced rather than set_values(): files declare the empty placeholder with any shape, even none at all
    if name in cdf:
        cdf._remove_variable(name)
    cdf.add_variable(name, values=values, is_nrv=is_nrv)


def with_virtuals(cdf: pycdfpp.CDF, master: pycdfpp.CDF) -> pycdfpp.CDF:
    """`cdf` with the values of every virtual variable of `master` it holds what to compute from.

    A virtual variable varies with records when its component does, or when a clone is made to.
    """
    for name, virtual in _in_dependency_order(master):
        if _component_name(virtual) in cdf:
            _set_values(cdf, name, _as_declared(FUNCTIONS[_function_name(virtual)](cdf, virtual), virtual),
                        is_nrv=cdf[_component_name(virtual)].is_nrv and not _makes_vary(cdf, virtual))
    return cdf


def has_computable_virtuals(dataset: DatasetIndex) -> bool:
    return any(getattr(p, 'FUNCT', '').lower() in FUNCTIONS for p in dataset.__dict__.values())


def _references(variable: pycdfpp.Variable) -> list[str]:
    return [a.value for _, a in variable.attributes.items() if isinstance(a.value, str)]


def _needed(variable: str, cdf: pycdfpp.CDF, master: pycdfpp.CDF) -> set[str]:
    """`variable` and every variable its attributes name (DEPEND_n, LABL_PTR_n, COMPONENT_n...), recursively."""
    needed, todo = set(), [variable]
    while todo:
        name = todo.pop()
        if name in needed or not (name in cdf or name in master):
            continue
        needed.add(name)
        todo += [ref for source in (cdf, master) if name in source for ref in _references(source[name])]
    return needed


def _keep_only(cdf: pycdfpp.CDF, names: set[str]) -> pycdfpp.CDF:
    for name in [n for n in cdf.keys() if n not in names]:
        cdf._remove_variable(name)
    return cdf


def pruned(variable: str, cdf: pycdfpp.CDF, master: pycdfpp.CDF) -> tuple[pycdfpp.CDF, pycdfpp.CDF]:
    """Both CDFs down to what `variable` needs: the variables left out are never decompressed, nor written back."""
    needed = _needed(variable, cdf, master)
    return _keep_only(cdf, needed), _keep_only(master, needed)


@CacheCall(cache_retention=timedelta(hours=12), is_pure=True)
def read_with_virtuals(url: Optional[str], variable: str, master_cdf_url: str) -> Optional[SpeasyVariable]:
    if url is None:
        return None
    cdf = with_virtuals(*pruned(variable, _load(url), _load(master_cdf_url)))
    loaded = get_codec('application/x-cdf').load_variables(variables=[variable], file=memoryview(pycdfpp.save(cdf)),
                                                           master_cdf_url=master_cdf_url)
    return loaded and loaded.get(variable)
