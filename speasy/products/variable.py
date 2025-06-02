from copy import deepcopy
from typing import Dict, List, Optional, Any, Tuple, Union

import astropy.table
import astropy.units
import numpy as np
import pandas as pds

from speasy.core.data_containers import (
    DataContainer,
    VariableAxis,
    VariableTimeAxis,
    _to_index
)
from speasy.plotting import Plot
from .base_product import SpeasyProduct


def _values(input: Any) -> Any:
    if isinstance(input, SpeasyVariable):
        return input.values
    return input


def _name(input: Any) -> str:
    if isinstance(input, SpeasyVariable):
        return input.name
    return str(input)


def _np_build_result_name(func, *args, **kwargs):
    return f"{func.__name__}({', '.join(map(_name, args))}{', ' * bool(kwargs)}{', '.join([f'{k}={_name(v)}' for k, v in kwargs.items()])})"


def _check_time_axis(axis: VariableTimeAxis, values: DataContainer):
    if not isinstance(axis, VariableTimeAxis):
        raise TypeError(
            f"axes[0] must be a VariableTimeAxis instance, got {type(axis)}"
        )
    if axis.shape[0] != values.shape[0]:
        raise ValueError(
            f"Time and data must have the same length, got time:{len(axis)} and data:{len(values)}"
        )


def _check_time_dependent_axis(axis: VariableAxis, axis_index, time_axis: VariableTimeAxis, values: DataContainer):
    if axis.shape[0] != len(time_axis):
        raise ValueError(
            f"Time dependent axis must have the same length than time axis, got {len(axis)} and {len(time_axis)}"
        )
    if axis.shape[1] != values.shape[axis_index]:
        raise ValueError(
            f"Axis {axis_index} must match data shape, got {axis.shape[1]} and {values.shape[axis_index]}"
        )


def _check_time_independent_axis(axis: VariableAxis, axis_index, values: DataContainer):
    if axis.shape[0] != values.shape[axis_index]:
        raise ValueError(
            f"Axis {axis_index} must match data shape, got {axis.shape[0]} and {values.shape[axis_index]}"
        )


def _check_extra_axes(time_axis: VariableTimeAxis, axes: List[VariableAxis], values: DataContainer):
    for index, axis in enumerate(axes):
        if not isinstance(axis, VariableAxis):
            raise TypeError(
                f"axes[1:] must be a VariableAxis instance, got {type(axis)}"
            )
        if axis.is_time_dependent:
            _check_time_dependent_axis(axis, index + 1, time_axis, values)
        else:
            _check_time_independent_axis(axis, index + 1, values)


def _check_axes(axes: List[VariableAxis or VariableTimeAxis], values: DataContainer):
    _check_time_axis(axes[0], values)
    _check_extra_axes(axes[0], axes[1:], values)


class SpeasyVariable(SpeasyProduct):
    """SpeasyVariable object. Base class for storing variable data.

    Attributes
    ----------
    time: numpy.ndarray
        time vector (x-axis data)
    values: numpy.ndarray
        data
    meta: Optional[dict]
        metadata
    columns: Optional[List[str]]
        column names, might be empty for spectrograms or 3D+ data
    axes: List[np.ndarray]
        Collection composed of time axis plus eventual additional axes according to values' shape
    axes_labels: List[str]
        Axes names
    unit: str
        Values physical unit
    name: str
        SpeasyVariable name
    nbytes: int
        memory usage in bytes
    fill_value: Any
        fill value if found in meta-data
    valid_range: Tuple[Any, Any]
        valid range if found in meta-data

    Methods
    -------
    view:
        Returns a view of the current variable within the desired :data:`index_range`
    to_dataframe:
        Converts the variable to a pandas.DataFrame object
    from_dataframe:
        Builds a SpeasyVariable from a pandas.DataFrame object
    to_astropy_table:
        Converts the variable to an astropy.table.Table
    unit_applied:
        Returns a copy where values are astropy.units.Quantity
    filter_columns:
        Returns a copy only containing selected columns
    replace_fillval_by_nan:
        Returns a SpeasyVaraible with NaN instead of fill value if fill value is set in meta data
    plot:
        Plot the data with matplotlib by default
    to_dictionary:
        Converts a SpeasyVariable to a Python dictionary, mostly used for serialization purposes
    copy:
        Returns a copy

    """

    __slots__ = ["__values_container", "__columns", "__axes"]
    __LIKE_NP_FUNCTIONS__ = {'zeros_like', 'empty_like', 'ones_like'}

    def __init__(
        self,
        axes: List[VariableAxis or VariableTimeAxis],
        values: DataContainer,
        columns: Optional[List[str]] = None,
    ):
        super().__init__()
        _check_axes(axes, values)

        if not isinstance(values, DataContainer):
            raise TypeError(
                f"values must be a DataContainer instance, got {type(values)}"
            )

        self.__columns = list(map(str.strip, columns or []))
        if values.ndim == 1:
            # to be consistent with pandas
            values = values.reshape((-1, 1))

        self.__values_container = values
        self.__axes = axes

    def view(self, index_range: Union[slice, np.ndarray]) -> "SpeasyVariable":
        """Return view of the current variable within the desired :data:`index_range`.

        Parameters
        ----------
        index_range: slice
            index range

        Returns
        -------
        speasy.common.variable.SpeasyVariable
            view of the variable on the given range
        """
        if (type(index_range) is np.ndarray) and (index_range.dtype == bool):
            index_range = np.all(index_range, axis=tuple(range(1, index_range.ndim)), keepdims=False)
        return SpeasyVariable(
            axes=[
                axis[index_range] if axis.is_time_dependent else axis
                for axis in self.__axes
            ],
            values=self.__values_container[index_range],
            columns=self.columns,
        )

    def copy(self, name=None) -> "SpeasyVariable":
        """Makes a deep copy the variable

        Parameters
        ----------
        name: str, optional
            new variable name, by default None, keeps the same name

        Returns
        -------
        SpeasyVariable
            deep copy the variable
        """
        return SpeasyVariable(
            axes=deepcopy(self.__axes),
            values=self.__values_container.copy(name=name),
            columns=deepcopy(self.columns),
        )

    def filter_columns(self, columns: List[str]) -> "SpeasyVariable":
        """Builds a SpeasyVariable with only selected columns

        Parameters
        ----------
        columns : List[str]
            list of column names to keep

        Returns
        -------
        SpeasyVariable
            a SpeasyVariable with only selected columns
        """
        indexes = list(map(lambda v: self.__columns.index(v), columns))
        return SpeasyVariable(
            axes=deepcopy(self.__axes),
            values=DataContainer(
                is_time_dependent=self.__values_container.is_time_dependent,
                name=self.__values_container.name,
                meta=deepcopy(self.__values_container.meta),
                values=self.__values_container.values[:, indexes],
            ),
            columns=columns,
        )

    def __eq__(self, other: Union["SpeasyVariable", float, int]) -> bool:
        """Check if this variable equals another. Or apply the numpy array comparison if other is a scalar.

        Parameters
        ----------
        other: speasy.common.variable.SpeasyVariable, float, int
            SpeasyVariable or scalar to compare with

        Returns
        -------
        bool, np.ndarray
            True if both variables are equal or an array with the element wise comparison between values and the given scalar
        """
        if type(other) is SpeasyVariable:
            return self.__axes == other.__axes and self.__values_container == other.__values_container
        else:
            return self.values.__eq__(other)

    def __ne__(self, other: Union["SpeasyVariable", float, int]) -> bool:
        if type(other) is SpeasyVariable:
            return not (other == self)
        else:
            return self.values.__ne__(other)

    def __len__(self):
        return len(self.__axes[0])

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(
                slice(_to_index(key.start, self.time),
                      _to_index(key.stop, self.time))
            )
        if type(key) in (list, tuple):
            if type(key[0]) is np.ndarray:
                return self.view(key[0])
            elif all(map(lambda v: type(v) is str, key)):
                return self.filter_columns(key)
        if type(key) is str and key in self.__columns:
            return self.filter_columns([key])
        if type(key) is np.ndarray:
            return self.view(key)
        raise ValueError(
            f"No idea how to slice SpeasyVariable with given value: {key}")

    def __setitem__(self, k, v: Union["SpeasyVariable", float, int]):
        if type(v) is SpeasyVariable:
            self.__values_container[k] = v.__values_container
            for axis, src_axis in zip(self.__axes, v.__axes):
                if axis.is_time_dependent:
                    axis[k] = src_axis
        else:
            self.__values_container[k] = v

    def __ge__(self, other):
        return np.greater_equal(self, other)

    def __gt__(self, other):
        return np.greater(self, other)

    def __le__(self, other):
        return np.less_equal(self, other)

    def __lt__(self, other):
        return np.less(self, other)

    def __mul__(self, other):
        return np.multiply(self, other)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __pow__(self, power, modulo=None):
        return np.power(self, power)

    def __add__(self, other):
        if type(other) is np.timedelta64:
            result = self.copy(name=f"shifted({self.name}, {other})")
            result.time[:] += other
            return result
        return np.add(self, other)

    def __radd__(self, other):
        if type(other) is np.timedelta64:
            raise ValueError(
                "timedelta64 +  SpeasyVariable is not supported, only SpeasyVariable + timedelta64 is supported")
        return np.add(other, self)

    def __sub__(self, other):
        if type(other) is np.timedelta64:
            result = self.copy(name=f"shifted({self.name}, -{other})")
            result.time[:] -= other
            return result
        return np.subtract(self, other)

    def __rsub__(self, other):
        if type(other) is np.timedelta64:
            raise ValueError(
                "timedelta64 -  SpeasyVariable is not supported, only SpeasyVariable - timedelta64 is supported")
        return np.subtract(other, self)

    def __truediv__(self, other):
        return np.divide(self, other)

    def __rtruediv__(self, other):
        return np.divide(other, self)

    def __np_build_axes__(self, other, axis=None):
        if axis is None or self.ndim == other.ndim:
            return deepcopy(self.__axes)
        else:
            axes = []
            for i, ax in enumerate(self.__axes):
                if i != axis:
                    axes.append(deepcopy(ax))
            return axes

    def __array_function__(self, func, types, args, kwargs):
        if func.__name__ in SpeasyVariable.__LIKE_NP_FUNCTIONS__:
            return SpeasyVariable.__dict__[func.__name__].__func__(self)
        if 'out' in kwargs:
            raise ValueError("out parameter is not supported")
        f_args = [_values(arg) for arg in args]
        f_kwargs = {name: _values(value) for name, value in kwargs.items()}
        res = func(*f_args, **f_kwargs)
        if np.isscalar(res):
            return res
        if isinstance(res, np.ndarray):
            if len(res.shape) != self.shape and (res.shape[0] != len(self.time) or kwargs.get('axis', None) == 0):
                return res

        n_cols = res.shape[1] if len(res.shape) > 1 else 1
        return SpeasyVariable(
            axes=self.__np_build_axes__(res, axis=kwargs.get('axis', None)),
            values=DataContainer(values=res,
                                 name=_np_build_result_name(func, *args, **kwargs),
                                 meta=deepcopy(self.__values_container.meta)),
            columns=[f"column_{i}" for i in range(n_cols)],
        )

    def __array_ufunc__(self, ufunc, method, *inputs, out: 'SpeasyVariable' or None = None, **kwargs):
        if out is not None:
            _out = _values(out[0])
        else:
            _out = None
        values = ufunc(*list(map(_values, inputs)), **{name: _values(value) for name, value in kwargs}, out=_out)

        axes = self.__np_build_axes__(values, axis=kwargs.get('axis', None))

        if out is not None:
            if isinstance(out, SpeasyVariable):
                out.__axes = axes
            return out
        if type(values) is np.ndarray and values.dtype == bool:
            return np.all(values, axis=tuple(range(1, values.ndim)), keepdims=True)
        else:
            return SpeasyVariable(
                axes=axes,
                values=DataContainer(values=values,
                                     name=_np_build_result_name(ufunc, *inputs, **kwargs),
                                     meta=deepcopy(self.__values_container.meta)),
                columns=[f"column_{i}" for i in range(values.shape[1])],
            )

    @property
    def ndim(self):
        return self.__values_container.ndim

    @property
    def shape(self):
        return self.__values_container.shape

    @property
    def dtype(self):
        return self.__values_container.dtype

    def astype(self, dtype) -> "SpeasyVariable":
        """Returns a SpeasyVariable with values converted to given dtype

        Parameters
        ----------
        dtype : str or np.dtype or type
            desired dtype

        Returns
        -------
        SpeasyVariable
            SpeasyVariable with values converted to given dtype
        """
        return SpeasyVariable(
            axes=deepcopy(self.__axes),
            values=self.__values_container.astype(dtype),
            columns=deepcopy(self.__columns),
        )

    @property
    def name(self) -> str:
        """SpeasyVariable name

        Returns
        -------
        str
            SpeasyVariable name
        """
        return self.__values_container.name

    @property
    def values(self) -> np.array:
        """SpeasyVariable values

        Returns
        -------
        np.array
            SpeasyVariable values
        """
        return self.__values_container.values

    @property
    def time(self) -> np.array:
        """Time axis values, equivalent to var.axes[0].values

        Returns
        -------
        np.array
            time axis values as numpy array of datetime64[ns]
        """
        return self.__axes[0].values

    @property
    def meta(self) -> Dict:
        """SpeasyVariable meta-data

        Returns
        -------
        Dict
            SpeasyVariable meta-data
        """
        return self.__values_container.meta

    @property
    def axes(self) -> List[VariableTimeAxis or VariableAxis]:
        """SpeasyVariable axes, axis 0 is always a VariableTimeAxis, there should be the same number of axes than values dimensions

        Returns
        -------
        List[VariableTimeAxis or VariableAxis]
            list of variable axes
        """
        return self.__axes

    @property
    def axes_labels(self) -> List[str]:
        """Axes names respecting axes order

        Returns
        -------
        List[str]
            list of axes names
        """
        return [axis.name for axis in self.__axes]

    @property
    def columns(self) -> List[str]:
        """SpeasyVariable columns names when it makes sense

        Returns
        -------
        List[str]
            list of columns names
        """
        return self.__columns

    @property
    def unit(self) -> str:
        """SpeasyVariable unit if found in meta-data

        Returns
        -------
        str
            unit if found in meta-data
        """
        return self.__values_container.unit

    @property
    def nbytes(self) -> int:
        """SpeasyVariable's values and axes memory usage

        Returns
        -------
        int
            number of bytes used to store values and axes
        """
        return self.__values_container.nbytes + np.sum(
            list(map(lambda ax: ax.nbytes, self.__axes))
        )

    @property
    def fill_value(self) -> Optional[Any]:
        """SpeasyVariable fill value if found in meta-data

        Returns
        -------
        Any
            fill value if found in meta-data
        """
        return self.meta.get("FILLVAL", None)

    @property
    def valid_range(self) -> Optional[Tuple[Any, Any]]:
        """SpeasyVariable valid range if found in meta-data

        Returns
        -------
        Tuple[Any, Any]
            valid range if found in meta-data
        """
        return self.meta.get("VALIDMIN", None), self.meta.get("VALIDMAX", None)

    def unit_applied(self, unit: str or None = None, copy=True) -> "SpeasyVariable":
        """Returns a SpeasyVariable with given or automatically found unit applied to values

        Parameters
        ----------
        unit : str or None, optional
            Use given unit or gets one from variable metadata, by default None
        copy : bool, optional
            Preserves source variable and returns a modified copy if true, by default True

        Returns
        -------
        SpeasyVariable
            SpeasyVariable identic to source one with values converted to astropy.units.Quantity according to given or found unit

        Notes
        -----
        This interface assume that there is only one unit for the whole variable since all stored in the same array

        See Also
        --------
        unit: returns variable unit if found in meta-data
        """
        if copy:
            axes = deepcopy(self.__axes)
            values = deepcopy(self.__values_container)
            columns = deepcopy(self.__columns)
        else:
            axes = self.__axes
            values = self.__values_container
            columns = self.__columns
        return SpeasyVariable(
            axes=axes, values=values.unit_applied(unit), columns=columns
        )

    def to_astropy_table(self) -> astropy.table.Table:
        """Convert the variable to an astropy.Table object.

        Parameters
        ----------
        datetime_index: bool
            boolean indicating that the index is datetime

        Returns
        -------
        astropy.Table:
            Variable converted to astropy.Table

        See Also
        --------
        from_dataframe: builds a SpeasyVariable from a pandas DataFrame
        to_dataframe: exports a SpeasyVariable to a pandas DataFrame
        """
        try:
            units = astropy.units.Unit(self.meta["UNITS"])
        except (ValueError, KeyError):
            units = None
        df = self.to_dataframe()
        umap = {c: units for c in df.columns}
        return astropy.table.Table.from_pandas(df, units=umap, index=True)

    def to_dataframe(self) -> pds.DataFrame:
        """Convert the variable to a pandas.DataFrame object.

        Returns
        -------
        pandas.DataFrame:
            Variable converted to Pandas DataFrame

        See Also
        --------
        from_dataframe: builds a SpeasyVariable from a pandas DataFrame
        to_astropy_table: exports a SpeasyVariable to an astropy.Table object
        """
        if len(self.__values_container.shape) != 2:
            raise ValueError(
                f"Cant' convert a SpeasyVariable with shape {self.__values_container.shape} to DataFrame, only 1D/2D variables are accepted"
            )
        return pds.DataFrame(
            index=self.time, data=self.values, columns=self.__columns, copy=True
        )

    @staticmethod
    def from_dataframe(df: pds.DataFrame) -> "SpeasyVariable":
        """Load from pandas.DataFrame object.

        Parameters
        ----------
        df: pandas.DataFrame
            Input DataFrame to convert

        Returns
        -------
        SpeasyVariable:
            Variable created from DataFrame

        See Also
        --------
        to_dataframe: exports a SpeasyVariable to a pandas DataFrame
        to_astropy_table: exports a SpeasyVariable to an astropy.Table object
        """
        if df.index.dtype == np.dtype("datetime64[ns]"):
            time = np.array(df.index)
        elif hasattr(df.index[0], "timestamp"):
            time = np.array(
                [np.datetime64(d.timestamp() * 1e9, "ns") for d in df.index]
            )
        else:
            raise ValueError(
                "Can't convert DataFrame index to datetime64[ns] array")
        return SpeasyVariable(
            axes=[VariableTimeAxis(values=time, meta={})],
            values=DataContainer(values=df.values, meta={}, name="Unknown"),
            columns=list(df.columns),
        )

    def to_dictionary(self, array_to_list=False) -> Dict[str, object]:
        """Converts SpeasyVariable to dictionary

        Parameters
        ----------
        array_to_list : bool, optional
            Converts numpy arrays to Python Lists when true, by default False

        Returns
        -------
        Dict[str, object]

        See Also
        --------
        from_dictionary: builds variable from dictionary
        """
        return {
            "axes": [
                axis.to_dictionary(array_to_list=array_to_list) for axis in self.__axes
            ],
            "values": self.__values_container.to_dictionary(
                array_to_list=array_to_list
            ),
            "columns": deepcopy(self.__columns),
        }

    @staticmethod
    def from_dictionary(dictionary: Dict[str, object] or None) -> "SpeasyVariable" or None:
        """Builds a SpeasyVariable from a well formed dictionary

        Returns
        -------
        SpeasyVariable or None

        See Also
        --------
        to_dictionary: exports SpeasyVariable to dictionary
        """
        if dictionary is not None:
            axes = dictionary["axes"]
            axes = [VariableTimeAxis.from_dictionary(axes[0])] + [
                VariableAxis.from_dictionary(axis) for axis in axes[1:]
            ]

            return SpeasyVariable(
                values=DataContainer.from_dictionary(dictionary["values"]),
                axes=axes,
                columns=dictionary.get("columns", None),
            )
        else:
            return None

    @property
    def plot(self, *args, **kwargs):
        """Plot the variable, tries to do its best to detect variable type and to populate plot labels

        """
        return Plot(
            values=self.__values_container, columns_names=self.columns, axes=self.axes
        )

    def replace_fillval_by_nan(self, inplace=False, convert_to_float=False) -> "SpeasyVariable":
        """Replaces fill values by NaN, non float values are automatically converted to float if convert_to_float is True.
        Fill value is taken from metadata field "FILLVAL"

        Parameters
        ----------
        inplace : bool, optional
            Modifies source variable when true else modifies and returns a copy, by default False
        convert_to_float : bool, optional
            Automatically converts variable to float if true and needed, by default False.

        Returns
        -------
        SpeasyVariable
            source variable or copy with fill values replaced by NaN

        See Also
        --------
        clamp_with_nan: replaces values outside valid range by NaN
        sanitized: removes fill and invalid values
        """
        # @TODO replace by a match case when Python 3.9 is EOL
        if inplace:
            res = self
            if convert_to_float and not np.issubdtype(self.dtype, np.floating):
                res.__values_container = res.__values_container.astype(float)
        else:
            if convert_to_float and not np.issubdtype(self.dtype, np.floating):
                res = self.astype(float)
            else:
                res = deepcopy(self)
        if (fill_value := self.fill_value) is not None:
            if convert_to_float and not np.issubdtype(res.dtype, np.floating):
                res.__values_container = res.__values_container.astype(float)
            res[res == fill_value] = np.nan
        return res

    def clamp_with_nan(self, inplace=False, valid_min=None, valid_max=None, convert_to_float=False) -> "SpeasyVariable":
        """Replaces values outside valid range by NaN, valid range is taken from metadata fields "VALIDMIN" and "VALIDMAX".
        Automatically converts variable to float if convert_to_float is True and needed.

        Parameters
        ----------
        inplace : bool, optional
            Modifies source variable when true else modifies and returns a copy, by default False
        valid_min : Float, optional
            Optional minimum valid value, takes metadata field "VALIDMIN" if not provided, by default None
        valid_max : Float, optional
            Optional maximum valid value, takes metadata field "VALIDMAX" if not provided, by default None
        convert_to_float : bool, optional
            Automatically converts variable to float if true and needed, by default False.

        Returns
        -------
        SpeasyVariable
            source variable or copy with values clamped by NaN

        See Also
        --------
        replace_fillval_by_nan: replaces fill values by NaN
        sanitized: removes fill and invalid values
        """
        # @TODO replace by a match case when Python 3.9 is EOL
        if inplace:
            res = self
            if convert_to_float and not np.issubdtype(self.dtype, np.floating):
                res.__values_container = res.__values_container.astype(float)
        else:
            if convert_to_float and not np.issubdtype(self.dtype, np.floating):
                res = self.astype(float)
            else:
                res = deepcopy(self)
        valid_min = valid_min or self.valid_range[0]
        valid_max = valid_max or self.valid_range[1]
        res[np.logical_or(res > valid_max, res < valid_min)] = np.nan
        return res

    def sanitized(self, drop_fill_values=True, drop_out_of_range_values=True, drop_nan_and_inf=True, valid_min=None,
                  valid_max=None) -> "SpeasyVariable":
        """Returns a copy of the variable with fill values and invalid values removed

        Parameters
        ----------
        drop_fill_values : bool, optional
            Remove fill values, by default True
        drop_out_of_range_values : bool, optional
            Remove values outside valid range, by default True
        drop_nan_and_inf : bool, optional
            Remove NaN and Infinite values, by default True
        valid_min : Float, optional
            Minimum valid value, takes metadata field "VALIDMIN" if not provided, by default None
        valid_max : Float, optional
            Maximum valid value, takes metadata field "VALIDMAX" if not provided, by default None

        Returns
        -------
        SpeasyVariable
            source variable or copy with fill and invalid values removed

        See Also
        --------
        replace_fillval_by_nan: replaces fill values by NaN
        clamp_with_nan: replaces values outside valid range by NaN
        """
        indexes = []
        if drop_nan_and_inf:
            indexes.append(np.isfinite(self).reshape(-1))
        if drop_fill_values and self.fill_value is not None:
            indexes.append(np.all(self != self.fill_value, axis=tuple(range(1, self.ndim))))
        if drop_out_of_range_values:
            valid_min = valid_min or self.valid_range[0]
            valid_max = valid_max or self.valid_range[1]
            if valid_min is not None and valid_max is not None:
                indexes.append(np.logical_and(
                    self >= valid_min, self <= valid_max
                ).reshape(-1))
        if len(indexes) == 0:
            raise ValueError(
                "No filtering applied, please set at least one of drop_fill_values, drop_out_of_range_values or drop_nan_and_inf to True")
        return self[
            np.logical_and.reduce(indexes)
        ]

    @staticmethod
    def reserve_like(other: "SpeasyVariable", length: int = 0) -> "SpeasyVariable":
        """Create a SpeasyVariable of given length and with the same properties than given variable but unset values

        Parameters
        ----------
        other : SpeasyVariable
            variable used as reference for shape and meta-data
        length : int, optional
            output variable length, by default 0

        Returns
        -------
        SpeasyVariable
            a SpeasyVariable similar to given one of given length
        """
        axes = []
        for axis in other.__axes:
            if axis.is_time_dependent:
                new_axis = type(axis).reserve_like(axis, length)
                axes.append(new_axis)
            else:
                axes.append(deepcopy(axis))
        return SpeasyVariable(
            values=DataContainer.reserve_like(
                other.__values_container, length),
            axes=axes,
            columns=other.columns,
        )

    @staticmethod
    def empty_like(other: "SpeasyVariable") -> "SpeasyVariable":
        """Create a SpeasyVariable with the same properties than given variable but unset values

        Parameters
        ----------
        other : SpeasyVariable
            variable used as reference for shape and meta-data

        Returns
        -------
        SpeasyVariable
            a SpeasyVariable similar to given one
        """
        return SpeasyVariable(
            values=DataContainer.empty_like(other.__values_container),
            axes=deepcopy(other.__axes),
            columns=deepcopy(other.columns),
        )

    @staticmethod
    def zeros_like(other: "SpeasyVariable") -> "SpeasyVariable":
        """Create a SpeasyVariable with the same properties than given variable but filled with zeros

        Parameters
        ----------
        other : SpeasyVariable
            variable used as reference for shape and meta-data

        Returns
        -------
        SpeasyVariable
            a SpeasyVariable similar to given one filled with zeros
        """
        return SpeasyVariable(
            values=DataContainer.zeros_like(other.__values_container),
            axes=deepcopy(other.__axes),
            columns=deepcopy(other.columns),
        )

    @staticmethod
    def ones_like(other: "SpeasyVariable") -> "SpeasyVariable":
        """Create a SpeasyVariable with the same properties than given variable but filled with ones

        Parameters
        ----------
        other : SpeasyVariable
            variable used as reference for shape and meta-data

        Returns
        -------
        SpeasyVariable
            a SpeasyVariable similar to given one filled with ones
        """
        return SpeasyVariable(
            values=DataContainer.ones_like(other.__values_container),
            axes=deepcopy(other.__axes),
            columns=deepcopy(other.columns),
        )

    def _repr_pretty_(self, p, cycle):
        import humanize
        if cycle:
            p.text("SpeasyVariable(...)")
        else:
            def _print_member(name, value, last=False):
                p.text(f"{name}: ")
                p.pretty(value)
                if not last:
                    p.text(", ")
                p.breakable()

            def _print_dict(name, d, last=False):
                p.text(f"{name}: ")
                with p.group(4, '{', '}'):
                    p.breakable()
                    for k, v in d.items():
                        p.text(f"{k}: ")
                        p.pretty(v)
                        p.text(", ")
                        p.breakable()
                if not last:
                    p.text(", ")
                p.breakable()

            def _print_time_range():
                p.text(f"Time Range: {self.time[0]} - {self.time[-1]}")
                p.breakable()

            with p.group(4, f'{self.__class__.__name__}(', ')'):
                p.breakable()
                _print_member("Name", self.name)
                if len(self):
                    _print_time_range()
                _print_member("Shape", self.shape)
                _print_member("Unit", self.unit)
                _print_member("Columns", self.columns)
                _print_dict("Meta", self.meta)
                _print_member("Size", humanize.naturalsize(self.nbytes))


def to_dictionary(var: SpeasyVariable, array_to_list=False) -> Dict[str, object]:
    return var.to_dictionary(array_to_list=array_to_list)


def from_dictionary(dictionary: Dict[str, object] or None) -> SpeasyVariable or None:
    return SpeasyVariable.from_dictionary(dictionary)


def from_dataframe(df: pds.DataFrame) -> SpeasyVariable:
    """Convert a dataframe to SpeasyVariable.

    See Also
    --------
    SpeasyVariable.from_dataframe
    """
    return SpeasyVariable.from_dataframe(df)


def to_dataframe(var: SpeasyVariable) -> pds.DataFrame:
    """Convert a :class:`~speasy.common.variable.SpeasyVariable` to pandas.DataFrame.

    See Also
    --------
    SpeasyVariable.to_dataframe
    """
    return SpeasyVariable.to_dataframe(var)


def merge(variables: List[SpeasyVariable]) -> Optional[SpeasyVariable]:
    """Merge a list of :class:`~speasy.common.variable.SpeasyVariable` objects.

    Parameters
    ----------
    variables: List[SpeasyVariable]
        Variables to merge together

    Returns
    -------
    SpeasyVariable:
        Resulting variable from merge operation
    """
    if len(variables) == 0:
        return None
    sorted_var_list = [v for v in variables if (
        v is not None) and (len(v.time) > 0)]
    sorted_var_list.sort(key=lambda v: v.time[0])

    # drop variables covered by previous ones
    for prev, current in zip(sorted_var_list[:-1], sorted_var_list[1:]):
        if prev.time[-1] >= current.time[-1]:
            sorted_var_list.remove(current)

    # drop variables covered by next ones
    for current, nxt in zip(sorted_var_list[:-1], sorted_var_list[1:]):
        if nxt.time[0] == current.time[0] and nxt.time[-1] >= current.time[-1]:
            sorted_var_list.remove(current)

    if len(sorted_var_list) == 0:
        for v in variables:
            if v is not None:
                return SpeasyVariable.reserve_like(v, length=0)
        return None

    overlaps = [
        np.where(current.time >= nxt.time[0])[0][0]
        if current.time[-1] >= nxt.time[0]
        else -1
        for current, nxt in zip(sorted_var_list[:-1], sorted_var_list[1:])
    ]

    dest_len = int(
        np.sum(
            [
                overlap if overlap != -1 else len(r.time)
                for overlap, r in zip(overlaps, sorted_var_list[:-1])
            ]
        )
    )
    dest_len += len(sorted_var_list[-1].time)

    result = SpeasyVariable.reserve_like(sorted_var_list[0], dest_len)

    pos = 0

    for r, overlap in zip(sorted_var_list, overlaps + [-1]):
        frag_len = len(r.time) if overlap == -1 else overlap
        result[pos: (pos + frag_len)] = r[0:frag_len]
        pos += frag_len
    return result


def same_time_axis(variables: List[SpeasyVariable]) -> bool:
    """Check if all variables have the same time axis values and length
    If only one variable is provided, it returns True.

    Parameters
    ----------
    variables : List[SpeasyVariable]
        list of variables to check

    Returns
    -------
    bool
        True if all variables have the same time axis values and length
    """
    if len(variables) < 2:
        return True
    ref_time_axis = variables[0].time
    return all([np.all(var.time == ref_time_axis) for var in variables[1:]])
