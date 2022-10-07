from copy import deepcopy
from typing import Dict, List, Optional

import astropy.table
import astropy.units
import numpy as np
import pandas as pds

from speasy.core.data_containers import (
    DataContainer,
    VariableAxis,
    VariableTimeAxis,
    _to_index,
)
from speasy.plotting import Plot

from .base_product import SpeasyProduct


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

    def __init__(
        self,
        axes: List[VariableAxis or VariableTimeAxis],
        values: DataContainer,
        columns: Optional[List[str]] = None,
    ):
        super().__init__()
        if not isinstance(axes[0], VariableTimeAxis):
            raise TypeError(
                f"axes[0] must be a VariableTimeAxis instance, got {type(axes[0])}"
            )
        if axes[0].shape[0] != values.shape[0]:
            raise ValueError(
                f"Time and data must have the same length, got time:{len(axes[0])} and data:{len(values)}"
            )

        self.__columns = list(map(str.strip, columns or []))
        if len(values.values.shape) == 1:
            # to be consistent with pandas
            values.reshape((values.shape[0], 1))

        self.__values_container = values
        self.__axes = axes

    def view(self, index_range: slice) -> "SpeasyVariable":
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
        return SpeasyVariable(
            axes=[
                axis[index_range] if axis.is_time_dependent else axis
                for axis in self.__axes
            ],
            values=self.__values_container[index_range],
            columns=self.columns,
        )

    def copy(self) -> "SpeasyVariable":
        """Makes a deep copy the variable

        Returns
        -------
        SpeasyVariable
            deep copy the variable
        """
        return SpeasyVariable(
            axes=deepcopy(self.__axes),
            values=deepcopy(self.__values_container),
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

    def __eq__(self, other: "SpeasyVariable") -> bool:
        """Check if this variable equals another.

        Parameters
        ----------
        other: speasy.common.variable.SpeasyVariable
            another SpeasyVariable object to compare with

        Returns
        -------
        bool:
            True if all attributes are equal
        """
        return (
            type(other) is SpeasyVariable
            and self.__axes == other.__axes
            and self.__values_container == other.__values_container
        )

    def __len__(self):
        return len(self.__axes[0])

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(
                slice(_to_index(key.start, self.time),
                      _to_index(key.stop, self.time))
            )
        if type(key) in (list, tuple) and all(map(lambda v: type(v) is str, key)):
            return self.filter_columns(key)
        if type(key) is str and key in self.__columns:
            return self.filter_columns([key])
        raise ValueError(
            f"No idea how to slice SpeasyVariable with given value: {key}")

    def __setitem__(self, k, v: "SpeasyVariable"):
        assert type(v) is SpeasyVariable
        self.__values_container[k] = v.__values_container
        for axis, src_axis in zip(self.__axes, v.__axes):
            if axis.is_time_dependent:
                axis[k] = src_axis

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

    def replace_fillval_by_nan(self, inplace=False) -> "SpeasyVariable":
        """Replaces fill values by NaN, non float values are automatically converted to float.
        Fill value is taken from metadata field "FILLVAL"

        Parameters
        ----------
        inplace : bool, optional
            Modifies source variable when true else modifies and returns a copy, by default False

        Returns
        -------
        SpeasyVariable
            source variable or copy with fill values replaced by NaN
        """
        if inplace:
            res = self
        else:
            res = deepcopy(self)
        if "FILLVAL" in res.meta:
            res.__values_container.replace_val_by_nan(res.meta["FILLVAL"])
        return res

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
