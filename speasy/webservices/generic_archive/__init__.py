# -*- coding: utf-8 -*-

"""cda package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import logging
from datetime import datetime, timedelta
from typing import Optional

from speasy.config import archive as cfg
from speasy.core import AllowedKwargs
from speasy.core.cache import Cacheable, CACHE_ALLOWED_KWARGS
from speasy.core.cdf.inventory_extractor import extract_parameters
from speasy.core.dataprovider import DataProvider, ParameterRangeCheck, GET_DATA_ALLOWED_KWARGS
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex, DatasetIndex
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
from speasy.core.requests_scheduling import SplitLargeRequests
from speasy.products.variable import SpeasyVariable

log = logging.getLogger(__name__)


def _global_inventory_dirs():
    from importlib import resources
    import os
    return os.path.join(str(resources.files('speasy')), "data/archive")


def get_or_make_node(path: str, root: SpeasyIndex) -> SpeasyIndex:
    parts = path.split('/', maxsplit=1)
    name = parts[0]
    if name not in root.__dict__:
        root.__dict__[name] = SpeasyIndex(name=name, provider='archive', uid='')
    if len(parts) == 1:
        return root.__dict__[name]
    return get_or_make_node(parts[1], root.__dict__[name])


def load_inventory_file(file: str, root: SpeasyIndex):
    import yaml
    entries = yaml.safe_load(file)
    for name, entry in entries.items():
        path = f"{entry['inventory_path']}/{name}"
        parent = get_or_make_node(entry['inventory_path'], root)
        dataset = DatasetIndex(name=name, provider='archive', uid=path)
        parent.__dict__[dataset.spz_name()] = dataset
        dataset.__dict__.update({p.spz_name(): p for p in extract_parameters(entry['master_cdf'], provider='archive',
                                                                             uid_fmt=f"{dataset.spz_uid()}/{{var_name}}")})


def _make_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    return f"{prefix}/{product}/{kwargs.get('coordinate_system', 'gse')}/{start_time}"


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"archive/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}'}


class GenericArchive(DataProvider):
    def __init__(self):
        DataProvider.__init__(self, provider_name='archive', provider_alt_names=['generic_archive', 'file'])

    def build_inventory(self, root: SpeasyIndex):
        from glob import glob
        lookup_dirs = _global_inventory_dirs() + cfg.extra_inventory_lookup_dirs.get()
        for lookup_dir in lookup_dirs:
            for file in glob(f"{lookup_dir}/*.y*ml"):
                load_inventory_file(file, root)
        return root

    def version(self, product):
        return 1

    def parameter_range(self, parameter_id: str or ParameterIndex) -> Optional[DateTimeRange]:
        """Get product time range.

        Parameters
        ----------
        parameter_id: str or ParameterIndex
            parameter id

        Returns
        -------
        Optional[DateTimeRange]
            Data time range

        Examples
        --------

        >>> import speasy as spz
        >>> spz.ssc.parameter_range("solarorbiter")
        <DateTimeRange: 2020-02-10T04:56:30+00:00 -> ...>

        """
        return self._parameter_range(parameter_id)

    def get_data(self, product: str, start_time: datetime, stop_time: datetime, **kwargs) -> Optional[SpeasyVariable]:
        var = self._get_data(product=product, start_time=start_time, stop_time=stop_time, **kwargs)
        return var

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS)
    @ParameterRangeCheck()
    @Cacheable(prefix="ssc_orbits", fragment_hours=lambda x: 24, version=version, entry_name=_make_cache_entry_name)
    @SplitLargeRequests(threshold=lambda x: timedelta(days=60))
    @Proxyfiable(GetProduct, get_parameter_args)
    def _get_data(self, product: str, start_time: datetime, stop_time: datetime) -> Optional[SpeasyVariable]:
        return None
