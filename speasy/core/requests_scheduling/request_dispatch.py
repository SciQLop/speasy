from typing import overload, Optional, Union, Iterable, Tuple, Mapping, List
from ...products import MaybeAnyProduct, TimeTable, Catalog, SpeasyVariable, Dataset
from .. import is_collection, all_of_type, progress_bar
from ..datetime_range import DateTimeRange
from speasy.core.inventory.indexes import SpeasyIndex, CatalogIndex, TimetableIndex, DatasetIndex, ParameterIndex, \
    ComponentIndex
from ...webservices import SSC_Webservice, AMDA_Webservice, CDA_Webservice, CSA_Webservice
from datetime import datetime
import numpy as np

TimeT = Union[str, datetime, float, np.datetime64]
TimeRangeT = Union[DateTimeRange, Tuple[TimeT, TimeT]]
TimeSerieIndexT = Union[ParameterIndex, ComponentIndex]

amda = AMDA_Webservice()
cda = CDA_Webservice()
ssc = SSC_Webservice()
csa = CSA_Webservice()

PROVIDERS = {
    'amda': amda,
    'cdaweb': cda,
    'cda': cda,
    'sscweb': ssc,
    'ssc': ssc,
    'csa': csa
}


def list_providers() -> List[str]:
    return list(PROVIDERS.keys())


@overload
def get_data(product: CatalogIndex, **kwargs) -> Catalog:
    ...


@overload
def get_data(product: TimetableIndex, **kwargs) -> TimeTable:
    ...


@overload
def get_data(product: str, **kwargs) -> TimeTable or Catalog:
    ...


@overload
def get_data(product: DatasetIndex, start_time: TimeT, stop_time: TimeT, **kwargs) -> Dataset or None:
    ...


@overload
def get_data(product: DatasetIndex, time_range: TimeRangeT, **kwargs) -> Dataset or None:
    ...


@overload
def get_data(product: DatasetIndex, time_range: Iterable[TimeRangeT], **kwargs) -> List[Dataset] or None:
    ...


@overload
def get_data(product: TimeSerieIndexT, start_time: TimeT, stop_time: TimeT, **kwargs) -> SpeasyVariable or None:
    ...


@overload
def get_data(product: TimeSerieIndexT, time_range: TimeRangeT, **kwargs) -> SpeasyVariable or None:
    ...


@overload
def get_data(product: TimeSerieIndexT, time_range: Iterable[TimeRangeT], **kwargs) -> List[SpeasyVariable] or None:
    ...


@overload
def get_data(product: Iterable[TimeSerieIndexT], start_time: TimeT, stop_time: TimeT,
             **kwargs) -> Mapping[str, SpeasyVariable] or None:
    ...


@overload
def get_data(product: TimeSerieIndexT, time_range: TimeRangeT, **kwargs) -> Mapping[str, SpeasyVariable] or None:
    ...


def _could_be_datetime(value):
    return type(value) in (str, datetime, np.datetime64, float)


def provider_and_product(path_or_product: str or SpeasyIndex) -> (str, str):
    """Breaks given product in two parts: provider and product UID

    Parameters
    ----------
    path_or_product : str or SpeasyIndex
        The product as SpeasyIndex or path as string you want to split
    Returns
    -------
    (str, str)
        the provider UID and the product UID
    """
    if isinstance(path_or_product, SpeasyIndex):
        return path_or_product.spz_provider().lower(), path_or_product.spz_uid()
    elif type(path_or_product) is str:
        if '/' in path_or_product:
            provider_uid, product_uid = path_or_product.split('/', 1)
            return provider_uid, product_uid
        else:
            raise ValueError(f"Given string does not look like a path {path_or_product}")
    raise TypeError(
        f"Wrong type for {path_or_product}, expecting a string or a SpeasyIndex, got {type(path_or_product)}")


def _scalar_get_data(index, *args, **kwargs):
    provider_uid, product_uid = provider_and_product(index)
    if provider_uid in PROVIDERS:
        return PROVIDERS[provider_uid].get_data(product_uid, *args, **kwargs)
    raise ValueError(f"Can't find a provider for {index}")


def _get_catalog_or_timetable(index, **kwargs):
    return _scalar_get_data(index, **kwargs)


def _get_timeserie1(index, dtrange, **kwargs):
    return _scalar_get_data(index, dtrange[0], dtrange[1], **kwargs)


def _get_timeserie2(index, start, stop, **kwargs):
    return _scalar_get_data(index, start, stop, **kwargs)


def _compile_args(*args, **kwargs):
    if len(args) == 0:
        if 'product' in kwargs:
            args = [kwargs.pop('product')]
    if len(args) == 1:
        if 'start_time' in kwargs and 'stop_time' in kwargs:
            args += [kwargs.pop('start_time'), kwargs.pop('stop_time')]
        elif 'time_range' in kwargs:
            args += [kwargs.pop('time_range')]
    return args, kwargs


def _is_dtrange(value):
    return type(value) is DateTimeRange or (
        hasattr(value, '__len__') and len(value) == 2 and _could_be_datetime(value[0]) and _could_be_datetime(value[1]))


def get_data(*args, **kwargs) -> MaybeAnyProduct:
    """Download given product, this function accepts string paths like "sscweb/moon" or index objects
    from inventory trees.

    Parameters
    ----------
    product : str or SpeasyIndex
        The product you want to download, either path like "sscweb/moon" or index objects.
    start_time : str or datetime.datetime, optional
        Start time, mandatory for time-series.
    stop_time : str or datetime.datetime, optional
        Stop time, mandatory for time-series.
    kwargs

    Returns
    -------
    MaybeAnyProduct
        The requested product if available or None

    Examples
    --------
    >>> moon=spz.get_data('sscweb/moon', '2000-01-01', '2000-09-02T12:00:00+00:00')
    >>> moon.columns
    ['X', 'Y', 'Z']
    >>> moon.data
               [[ 183940.73767809, -354329.74995782,   36559.09278865],
               [ 183989.39891203, -354307.09633046,   36558.99256677],
               [ 184038.04489285, -354284.42184423,   36558.88913279],
               ...,
               [ 230448.57392717,  305986.424528  ,   33999.47652102],
               [ 230405.72253792,  306023.74218105,   33998.89651167],
               [ 230362.93800137,  306061.10305253,   33998.32408929]]
    """

    args, kwargs = _compile_args(*args, **kwargs)
    if len(args) == 0:
        raise ValueError("You must at least provide a product to retrieve")

    product = args[0]
    if is_collection(product) and not isinstance(product, SpeasyIndex):
        return list(map(lambda p: get_data(p, *args[1:], **kwargs), progress_bar(leave=True, **kwargs)(product)))

    if len(args) == 1:
        return _get_catalog_or_timetable(*args, **kwargs)
    if len(args) == 2:
        t_range = args[1]
        if _is_dtrange(t_range):
            return _get_timeserie1(*args, **kwargs)
        if is_collection(t_range):
            return list(
                map(lambda r: get_data(product, r, *args[2:], **kwargs),
                    progress_bar(leave=False, **kwargs)(t_range)))
        return get_data(product, get_data(t_range), *args[2:], **kwargs)
    if len(args) == 3:
        return _get_timeserie2(*args, **kwargs)
