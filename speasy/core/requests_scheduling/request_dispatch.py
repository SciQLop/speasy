import os
import sys
from datetime import datetime
from typing import Iterable, List, Optional, Tuple, Union, overload

import numpy as np
import logging

from .. import is_collection, progress_bar
from ..datetime_range import DateTimeRange
from ..inventory.indexes import (CatalogIndex, ComponentIndex,
                                 DatasetIndex, ParameterIndex,
                                 SpeasyIndex, TimetableIndex)
from ...config import core as core_cfg, amda as amda_cfg
from ...products import *
from ...data_providers import (AmdaWebservice, CdaWebservice, CsaWebservice,
                               SscWebservice, GenericArchive)
from ..http import is_server_up

log = logging.getLogger(__name__)

TimeT = Union[str, datetime, float, np.datetime64]
TimeRangeT = Union[DateTimeRange, Tuple[TimeT, TimeT]]
TimeSerieIndexT = Union[ParameterIndex, ComponentIndex]
TimeRangeCollectionT = Union[TimetableIndex, CatalogIndex, Iterable[Iterable[Union[TimeT]]]]

PROVIDERS = {}
amda = None
csa = None
cda = None
ssc = None
archive = None


def init_amda(ignore_disabled_status=False):
    global amda
    if ignore_disabled_status or 'amda' not in core_cfg.disabled_providers():
        if AmdaWebservice.is_server_up():
            amda = AmdaWebservice()
            sys.modules[__name__].amda = amda
            PROVIDERS['amda'] = amda
        else:
            log.warning(f"AMDA server {amda_cfg.entry_point()} is down, disabling AMDA provider")


def init_csa(ignore_disabled_status=False):
    global csa
    if ignore_disabled_status or 'csa' not in core_cfg.disabled_providers():
        if is_server_up(CsaWebservice.BASE_URL):
            csa = CsaWebservice()
            sys.modules[__name__].csa = csa
            PROVIDERS['csa'] = csa
        else:
            log.warning(f"CSA server {CsaWebservice.BASE_URL} is down, disabling CSA provider")


def init_cdaweb(ignore_disabled_status=False):
    global cda
    if ignore_disabled_status or not core_cfg.disabled_providers().intersection({'cda', 'cdaweb'}):
        if is_server_up(CdaWebservice.BASE_URL):
            cda = CdaWebservice()
            sys.modules[__name__].cda = cda
            PROVIDERS['cda'] = cda
            PROVIDERS['cdaweb'] = cda
        else:
            log.warning(f"CDA server {CdaWebservice.BASE_URL} is down, disabling CDA provider")


def init_sscweb(ignore_disabled_status=False):
    global ssc
    if ignore_disabled_status or not core_cfg.disabled_providers().intersection({'ssc', 'sscweb'}):
        if is_server_up(SscWebservice.BASE_URL):
            ssc = SscWebservice()
            sys.modules[__name__].ssc = ssc
            PROVIDERS['ssc'] = ssc
            PROVIDERS['sscweb'] = ssc
        else:
            log.warning(f"SSC server {SscWebservice.BASE_URL} is down, disabling SSC provider")


def init_archive(ignore_disabled_status=False):
    global archive
    if ignore_disabled_status or not core_cfg.disabled_providers().intersection({'archive', 'generic_archive'}):
        archive = GenericArchive()
        sys.modules[__name__].archive = archive
        PROVIDERS['archive'] = archive
        PROVIDERS['generic_archive'] = archive


def init_providers(ignore_disabled_status=False):
    init_amda(ignore_disabled_status=ignore_disabled_status)
    init_csa(ignore_disabled_status=ignore_disabled_status)
    init_cdaweb(ignore_disabled_status=ignore_disabled_status)
    init_sscweb(ignore_disabled_status=ignore_disabled_status)
    init_archive(ignore_disabled_status=ignore_disabled_status)


if 'SPEASY_SKIP_INIT_PROVIDERS' not in os.environ:
    init_providers()


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
def get_data(product: DatasetIndex, time_range: Iterable[TimeRangeT], **kwargs) -> List[Optional[Dataset]] or None:
    ...


@overload
def get_data(product: TimeSerieIndexT, start_time: TimeT, stop_time: TimeT, **kwargs) -> SpeasyVariable or None:
    ...


@overload
def get_data(product: TimeSerieIndexT, time_range: TimeRangeT, **kwargs) -> SpeasyVariable or None:
    ...


@overload
def get_data(product: TimeSerieIndexT, time_range: Iterable[TimeRangeT], **kwargs) -> List[Optional[
    SpeasyVariable]] or None:
    ...


@overload
def get_data(product: TimeSerieIndexT, time_range: TimeRangeCollectionT, **kwargs) -> List[Optional[
    SpeasyVariable]] or None:
    ...


@overload
def get_data(product: Iterable[TimeSerieIndexT], start_time: TimeT, stop_time: TimeT,
             **kwargs) -> List[Optional[SpeasyVariable]] or None:
    ...


@overload
def get_data(product: Iterable[TimeSerieIndexT], time_range: TimeRangeCollectionT, **kwargs) -> List[List[
    Optional[SpeasyVariable]]] or None:
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
    """Retrieve requested product(s).
    Speasy gives access to two kind of products, time-dependent products such as physical measurements or trajectories
    and products such as timetables or event catalogs. So depending on which product you want to retrieve :func:`speasy.get_data`
    accepts different sets of arguments:

    - For time-independent products:

    .. highlight:: python
    .. code-block:: python

        get_data(product_or_products, **kwargs)

    - For time-dependent products:

    .. highlight:: python
    .. code-block:: python

        get_data(product_or_products, start_time, stop_time, **kwargs)
        get_data(product_or_products, datetime_range_or_datetime_range, **kwargs)

    Since get_data accepts both at the same time a list of products and a list of ranges, it will always iterate first
    on products then on datetime ranges. In other words, all products will be retrieved for all given datetime ranges.

    Parameters
    ----------
    args :
        Either a time independent or a list of time independent indexes or any combination of time dependent or list of
        time dependent indexes plus a datetime range or a list of datetime ranges. See examples below for more details.
    kwargs :
        For webservice specific keyword arguments check :doc:`/user/data_providers`.

        - disable_proxy: bool
            ignore proxy configuration and always bypass proxy server when True (default: False).
        - disable_cache: bool
            ignore cache content when True (default: False).
        - progress: bool
            show progress bar when True (default: False).

    Returns
    -------
        requested product(s) according to given parameters, either a single product or a collection of products.

    Examples
    --------

    - A simple parameter request on a single tile range:

    >>> import speasy as spz
    >>> spz.get_data("amda/imf_gsm", "2016-10-10", "2016-10-11")
    <speasy.products.variable.SpeasyVariable object at ...>


    - Same with a catalog using Speasy dynamic inventory:

    >>> import speasy as spz
    >>> amda_catalogs = spz.inventories.tree.amda.Catalogs
    >>> spz.get_data(amda_catalogs.SharedCatalogs.EARTH.model_regions_plasmas_cluster_2005)
    <Catalog: model_regions_plasmas_cluster_2005>

    - You can also request a collection of catalogs:

    >>> import speasy as spz
    >>> amda_catalogs = spz.inventories.tree.amda.Catalogs
    >>> spz.get_data([amda_catalogs.SharedCatalogs.EARTH.model_regions_plasmas_cluster_2005,
    ...               amda_catalogs.SharedCatalogs.EARTH.model_regions_plasmas_mms_2019])
    [<Catalog: model_regions_plasmas_cluster_2005>, <Catalog: model_regions_plasmas_mms_2019>]

    - You can also request a parameter for several intervals:

    >>> import speasy as spz
    >>> spz.get_data("amda/imf_gsm", [["2016-10-10", "2016-10-11"],
    ...                               ["2017-10-10", "2017-10-11"]])
    [<speasy.products.variable.SpeasyVariable object at ...>, <speasy.products.variable.SpeasyVariable object at ...>]

    - Several products on a single interval:

    >>> import speasy as spz
    >>> spz.get_data(["amda/imf_gsm", spz.inventories.tree.ssc.Trajectories.wind],
    ...              "2016-10-10", "2016-10-11")
    [<speasy.products.variable.SpeasyVariable object at ...>, <speasy.products.variable.SpeasyVariable object at ...>]

    - Several products for several time ranges:

    >>> import speasy as spz
    >>> data= spz.get_data(["amda/imf_gsm",
    ...                  spz.inventories.tree.ssc.Trajectories.wind],
    ...              [["2016-10-10", "2016-10-11"],
    ...               ["2017-10-10", "2017-10-11"]])
    >>> len(data), len(data[0])
    (2, 2)

    - A catalog or a timetable can also be used as time ranges collection to download a product:

    >>> import speasy as spz
    >>> amda_shared_tt = spz.inventories.tree.amda.TimeTables.SharedTimeTables
    >>> mex_inventory = spz.inventories.tree.amda.Parameters.MEX
    >>> mgs_inventory = spz.inventories.tree.amda.Parameters.MGS
    >>> conj_mex_mgs = spz.get_data(amda_shared_tt.MARS.conjonctions_mex_mgs_2004_0)
    >>> data = spz.get_data(
    ...                     [mex_inventory.ELS.mex_els_all.mex_els_spec,
    ...                      mgs_inventory.MAG.mgs_mag_mso.b_mgs_mso],
    ...                     conj_mex_mgs)
    >>> len(data), len(data[0])
    (2, 28)

    - Can even pass a CatalogIndex or a TimeTableIndex directly:

    >>> import speasy as spz
    >>> amda_shared_tt = spz.inventories.tree.amda.TimeTables.SharedTimeTables
    >>> mex_inventory = spz.inventories.tree.amda.Parameters.MEX
    >>> mgs_inventory = spz.inventories.tree.amda.Parameters.MGS
    >>> data = spz.get_data(
    ...                     [mex_inventory.ELS.mex_els_all.mex_els_spec,
    ...                      mgs_inventory.MAG.mgs_mag_mso.b_mgs_mso],
    ...                     amda_shared_tt.MARS.conjonctions_mex_mgs_2004_0)
    >>> len(data), len(data[0])
    (2, 28)

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
