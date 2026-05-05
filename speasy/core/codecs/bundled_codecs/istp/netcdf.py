from typing import List, AnyStr, Optional, Mapping, Union
import io
import os
import tempfile
import logging
from datetime import timedelta

import numpy as np
import pyistp

from speasy.core.codecs import CodecInterface, register_codec, Buffer
from speasy.core.cache import CacheCall
from speasy.products import SpeasyVariable

from . import _load_variable, _resolve_url_type

log = logging.getLogger(__name__)


def _load_variables(variables, file=None, buffer=None):
    istp_loader = pyistp.load_netcdf(file=file, buffer=buffer)
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
    except Exception:
        pass


def _write_time_axis(axis, ds) -> str:
    dim_name = axis.name
    if dim_name not in ds.dimensions:
        ds.createDimension(dim_name, len(axis.values))
    if dim_name not in ds.variables:
        var = ds.createVariable(dim_name, 'f8', (dim_name,))
        var.units = "seconds since 1970-01-01T00:00:00"
        var.VAR_TYPE = "support_data"
        var[:] = axis.values.astype('int64') / 1e9
        for k, val in axis.meta.items():
            if k != 'units':
                _try_set_attr(var, k, val)
    return dim_name


def _write_extra_axis(axis, time_dim_name: str, ds):
    ax_dim_name = f"dim_{axis.name}"
    if axis.is_time_dependent:
        dims = (time_dim_name, ax_dim_name)
        size = axis.values.shape[-1]
    else:
        dims = (ax_dim_name,)
        size = axis.values.shape[0]
    if ax_dim_name not in ds.dimensions:
        ds.createDimension(ax_dim_name, size)
    if axis.name not in ds.variables:
        var = ds.createVariable(axis.name, _nc_dtype(axis.values), dims)
        var[:] = axis.values
        for k, val in axis.meta.items():
            _try_set_attr(var, k, val)


def _write_variable_nc(v: SpeasyVariable, ds, written_axes: list):
    time_dim_name = _write_time_axis(v.axes[0], ds)
    var_dims = [time_dim_name]
    for ax in v.axes[1:]:
        if ax.name not in written_axes:
            _write_extra_axis(ax, time_dim_name, ds)
            written_axes.append(ax.name)
        var_dims.append(f"dim_{ax.name}")
    var = ds.createVariable(v.name, _nc_dtype(v.values), tuple(var_dims))
    var[:] = v.values
    for k, val in v.meta.items():
        _try_set_attr(var, k, val)
    # Re-assert DEPEND_* after meta loop: original values (e.g. "Epoch") may
    # differ from the names used in the saved file (e.g. "time").
    var.DEPEND_0 = time_dim_name
    for i, ax in enumerate(v.axes[1:], start=1):
        var.setncattr(f"DEPEND_{i}", ax.name)


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

    @property
    def supported_extensions(self) -> List[str]:
        return ["nc", "nc4"]

    @property
    def supported_mimetypes(self) -> List[str]:
        return ["application/x-netcdf", "application/netcdf"]

    @property
    def name(self) -> str:
        return self.__class__.__name__
