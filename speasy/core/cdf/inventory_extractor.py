import logging
from typing import List, Optional

import pyistp

from speasy.core.http import urlopen_with_retry
from speasy.core.inventory.indexes import ParameterIndex

log = logging.getLogger(__name__)


def filter_meta(datavar: pyistp.loader.DataVariable) -> dict:
    keep_list = ['CATDESC', 'FIELDNAM', 'UNITS', 'UNIT_PTR', 'DISPLAY_TYPE', 'LABLAXIS', 'LABL_PTR_1', 'LABL_PTR_2',
                 'LABL_PTR_3']
    base = {key: value for key, value in datavar.attributes.items() if key in keep_list}
    if len(datavar.values.shape) == 1:
        base['spz_shape'] = 1
    else:
        base['spz_shape'] = datavar.values.shape[1:]
    return base


def extract_parameter(cdf: pyistp.loader.ISTPLoader, var_name: str, provider: str, uid_fmt: str = "{var_name}") -> \
    Optional[ParameterIndex]:
    try:
        datavar = cdf.data_variable(var_name)
        if datavar is not None:
            return ParameterIndex(name=var_name, provider=provider, uid=uid_fmt.format(var_name=var_name),
                                  meta=filter_meta(datavar))
    except IndexError or RuntimeError:
        print(f"Issue loading {var_name} from {cdf}")

    return None


def extract_parameters(url: str, provider: str, uid_fmt: str = "{var_name}") -> List[ParameterIndex]:
    indexes: List[ParameterIndex] = []
    try:
        with urlopen_with_retry(url) as remote_cdf:
            cdf = pyistp.load(buffer=remote_cdf.read())
            return list(filter(lambda p: p is not None,
                               map(lambda var_name: extract_parameter(cdf, var_name, provider, uid_fmt),
                                   cdf.data_variables())))

    except RuntimeError:
        print(f"Issue loading {url}")
    return indexes
