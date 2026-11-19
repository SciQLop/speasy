from typing import List, AnyStr, Optional, Mapping, Union
import io
import os
import tempfile
import logging
import re
from datetime import timedelta

import numpy as np
import pyistp

from speasy.core.codecs import CodecInterface, register_codec, Buffer
from speasy.core.cache import CacheCall
from speasy.products import SpeasyVariable

from . import _load_variable, _resolve_url_type, _list_variables, _axis_slot, _attributes_to_write

log = logging.getLogger(__name__)
_PTR_rx = re.compile(r".*_PTR(_\d+)?")


def _load_variables(variables, file=None, buffer=None):
    istp_loader = pyistp.load(file=file, buffer=buffer)
    if istp_loader is not None:
        return {variable: _load_variable(istp_loader, variable) for variable in variables}
    return None


def _nc_dtype(arr: np.ndarray) -> str:
    kind = arr.dtype.kind
    itemsize = arr.dtype.itemsize
    if kind == 'f':
        return f'f{itemsize}'
    if kind in ('i', 'u'):
        return f'{kind}{itemsize}'
    return 'f8'


def _try_set_attr(nc_var, key, value):
    try:
        setattr(nc_var, key, value)
    except Exception as e:
        log.debug("Could not set netCDF attribute '%s': %s", key, e)


def _write_time_axis(axis, dim_name: str, ds):
    ds.createDimension(dim_name, len(axis.values))
    var = ds.createVariable(dim_name, 'f8', (dim_name,))
    var.units = "seconds since 1970-01-01T00:00:00"
    var.VAR_TYPE = "support_data"
    var[:] = axis.values.astype('int64') / 1e9
    for k, val in axis.meta.items():
        if k != 'units':
            _try_set_attr(var, k, val)


def _data_dimensions(v: SpeasyVariable, axis_names: List[str], ds) -> List[str]:
    """One dimension per dimension of the data, named after the axis describing it when there is one.

    Sizing them from the data rather than from the axes is what lets an axis span several of them.
    """
    names = [axis_names[0]]
    for index, size in enumerate(v.values.shape[1:], start=1):
        name = f"dim_{axis_names[index]}" if index < len(axis_names) else f"dim_{v.name}_{index}"
        if name not in ds.dimensions:
            ds.createDimension(name, size)
        names.append(name)
    return names


def _axis_dimensions(axis, axis_index: int, data_dims: List[str], data_shape) -> tuple:
    """The dimensions an axis spans: a coordinate grid covers several, a plain axis covers one."""
    if axis.values.shape == data_shape:
        return tuple(data_dims)
    if axis.values.shape == data_shape[1:]:
        return tuple(data_dims[1:])
    if axis.is_time_dependent:
        return data_dims[0], data_dims[axis_index]
    return (data_dims[axis_index],)


def _write_pointed_variable(name: str, values: list, ds) -> str:
    ds.createDimension(name, len(values))
    ds.createVariable(name, str, (name,))[:] = np.array([str(value) for value in values], dtype=object)
    return name


def _write_attribute(var, key: str, value, ds):
    if _PTR_rx.match(key) and isinstance(value, list):
        value = _write_pointed_variable(f"{var.name}_{key}", value, ds)
    _try_set_attr(var, key, value)


def _write_extra_axis(axis, name: str, dims: tuple, time_dim_name: str, ds):
    var = ds.createVariable(name, _nc_dtype(axis.values), dims)
    var[:] = axis.values
    for k, val in axis.meta.items():
        _try_set_attr(var, k, val)
    if axis.is_time_dependent:
        # this is how the reader tells a record varying axis from a fixed one
        var.DEPEND_0 = time_dim_name


def _write_variable_nc(v: SpeasyVariable, ds, saved_axes: list):
    slots = [_axis_slot(ax, saved_axes, taken=ds.variables) for ax in v.axes]
    axis_names = [name for name, _ in slots]
    if slots[0][1]:
        _write_time_axis(v.axes[0], axis_names[0], ds)
    var_dims = _data_dimensions(v, axis_names, ds)
    for index, (ax, (name, to_write)) in enumerate(zip(v.axes[1:], slots[1:]), start=1):
        if to_write:
            _write_extra_axis(ax, name, _axis_dimensions(ax, index, var_dims, v.values.shape), axis_names[0], ds)
    var = ds.createVariable(v.name, _nc_dtype(v.values), tuple(var_dims))
    var[:] = v.values
    for k, val in _attributes_to_write(v).items():
        _write_attribute(var, k, val, ds)
    # Re-assert DEPEND_* after meta loop: original values (e.g. "Epoch") may
    # differ from the names used in the saved file (e.g. "time").
    for i, name in enumerate(axis_names):
        var.setncattr(f"DEPEND_{i}", name)


def _fill_dataset(ds, variables: List[SpeasyVariable]):
    written_axes = []
    for v in variables:
        if not isinstance(v, SpeasyVariable):
            raise ValueError(f"Expected SpeasyVariable, got {type(v)}")
        _write_variable_nc(v, ds, written_axes)


@register_codec
class IstpNetCDF(CodecInterface):
    """Codec for ISTP NetCDF4 files. This codec is a wrapper around PyISTP library using the NetCDF4 driver."""

    def load_variables(self,
                       variables: List[AnyStr],
                       file: Union[Buffer, str, io.IOBase],
                       cache_remote_files=True,
                       **kwargs
                       ) -> Optional[Mapping[AnyStr, SpeasyVariable]]:
        kwargs["variables"] = variables
        kwargs.update((_resolve_url_type(file, prefix="", cache_remote_files=cache_remote_files),))
        return _load_variables(**kwargs)

    @CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
    def load_variable(self,
                      variable: AnyStr, file: Union[Buffer, str, io.IOBase],
                      cache_remote_files=True,
                      **kwargs
                      ) -> Optional[SpeasyVariable]:
        r = self.load_variables(variables=[variable], file=file,
                                cache_remote_files=cache_remote_files, **kwargs)
        if r is not None:
            return r.get(variable)
        return None

    def save_variables(self, variables: List[SpeasyVariable], file: Optional[Union[str, io.IOBase]] = None,
                       **kwargs) -> Union[bool, Buffer]:
        import netCDF4

        if isinstance(file, str):
            ds = netCDF4.Dataset(file, "w")
            _fill_dataset(ds, variables)
            ds.close()
            return True

        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.nc')
        try:
            os.close(tmp_fd)
            ds = netCDF4.Dataset(tmp_path, "w")
            _fill_dataset(ds, variables)
            ds.close()
            with open(tmp_path, 'rb') as f:
                data = f.read()
        finally:
            os.unlink(tmp_path)

        if isinstance(file, io.IOBase):
            file.write(data)
            return True
        return memoryview(data)

    def list_variables(self, file: Union[Buffer, str, io.IOBase]) -> List[str]:
        return _list_variables(file)

    @property
    def supported_extensions(self) -> List[str]:
        return ["nc", "nc4"]

    @property
    def supported_mimetypes(self) -> List[str]:
        return ["application/x-netcdf", "application/netcdf"]

    @property
    def name(self) -> str:
        return self.__class__.__name__
