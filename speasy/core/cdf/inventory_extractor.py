import logging
from datetime import timedelta
from typing import List, Optional, Union

import pyistp
from pyistp.loader import DataVariable, ISTPLoader
from speasy.core.any_files import any_loc_open
from speasy.core.cache import CacheCall
from speasy.core.inventory.indexes import ParameterIndex, DatasetIndex

log = logging.getLogger(__name__)


def filter_variable_meta(datavar: DataVariable) -> dict:
    keep_list = ['CATDESC', 'FIELDNAM', 'UNITS', 'UNIT_PTR', 'DISPLAY_TYPE', 'LABLAXIS', 'LABL_PTR_1', 'LABL_PTR_2',
                 'LABL_PTR_3', 'VIRTUAL', 'FUNCT', 'FILLVAL']
    base = {key: value for key, value in datavar.attributes.items() if key in keep_list}
    base['cdf_type'] = datavar.cdf_type
    if len(datavar.values.shape) == 1:
        base['spz_shape'] = 1
    else:
        base['spz_shape'] = datavar.values.shape[1:]
    return base


def _attribute_value(attr):
    if len(attr) == 1:
        return attr[0]
    else:
        return list(attr)


def filter_dataset_meta(dataset: ISTPLoader) -> dict:
    keep_list = ['Caveats', 'Rules_of_use', 'Time_resolution', 'spase_DatasetResourceID', 'HTTP_LINK', 'Data_type',
                 'Acknowledgement']
    return {key: _attribute_value(dataset.attribute(key)) for key in dataset.attributes() if key in keep_list}


def extract_parameter(cdf: ISTPLoader, var_name: str, provider: str, uid_fmt: str = "{var_name}", meta=None) -> \
    Optional[ParameterIndex]:
    try:
        datavar = cdf.data_variable(var_name)
        meta = meta or {}
        if datavar is not None:
            return ParameterIndex(name=var_name, provider=provider, uid=uid_fmt.format(var_name=var_name),
                                  meta={**filter_variable_meta(datavar), **meta})
    except IndexError or RuntimeError:
        print(f"Issue loading {var_name} from {cdf}")

    return None


def _extract_parameters_impl(cdf: ISTPLoader, provider: str, uid_fmt: str = "{var_name}", meta=None) -> List[
    ParameterIndex]:
    return list(filter(lambda p: p is not None,
                       map(lambda var_name: extract_parameter(cdf, var_name, provider, uid_fmt, meta=meta),
                           cdf.data_variables())))


def extract_parameters(url_or_istp_loader: Union[str,ISTPLoader], provider: str, uid_fmt: str = "{var_name}", meta=None) -> List[ParameterIndex]:
    indexes: List[ParameterIndex] = []
    try:
        if isinstance(url_or_istp_loader, str):
            with any_loc_open(url_or_istp_loader) as remote_cdf:
                cdf = pyistp.load(buffer=remote_cdf.read())
                return _extract_parameters_impl(cdf, provider=provider, uid_fmt=uid_fmt, meta=meta)
        else:
            return _extract_parameters_impl(url_or_istp_loader, provider=provider, uid_fmt=uid_fmt, meta=meta)

    except RuntimeError:
        print(f"Issue loading {url_or_istp_loader}")
    return indexes


@CacheCall(cache_retention=timedelta(days=7), is_pure=True)
def make_dataset_index(url: str, name: str, provider: str, uid: str, meta=None,
                       params_uid_format: str = "{var_name}", params_meta=None) -> Optional[DatasetIndex]:
    try:
        with any_loc_open(url, cache_remote_files=True) as remote_cdf:
            meta = meta or {}
            params_meta = params_meta or {}
            cdf = pyistp.load(buffer=remote_cdf.read())
            dataset = DatasetIndex(name=name, provider=provider, uid=uid, meta={**filter_dataset_meta(cdf), **meta})
            dataset.__dict__.update(
                {p.spz_name(): p for p in
                 _extract_parameters_impl(cdf, provider=provider, uid_fmt=params_uid_format, meta=params_meta)})
            return dataset
    except RuntimeError:
        print(f"Issue loading {url}")
    return None
