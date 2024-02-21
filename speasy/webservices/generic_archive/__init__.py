# -*- coding: utf-8 -*-

"""cda package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

import logging
from typing import Optional
from datetime import timedelta

from speasy.config import SPEASY_CONFIG_DIR
from speasy.config import archive as cfg
from speasy.core import AnyDateTimeType, AllowedKwargs
from speasy.core.cdf.inventory_extractor import make_dataset_index
from speasy.core.dataprovider import DataProvider, GET_DATA_ALLOWED_KWARGS
from speasy.core.direct_archive_downloader import get_product
from speasy.core.inventory.indexes import SpeasyIndex, ParameterIndex
from speasy.core.http import is_server_up
from speasy.core.url_utils import host_and_port, is_local_file
from speasy.products.variable import SpeasyVariable
from speasy.core.cache import CacheCall, CACHE_ALLOWED_KWARGS

log = logging.getLogger(__name__)


def _global_inventory_dir():
    import os
    return os.path.join(os.path.dirname(__file__), "../../data/archive")


def user_inventory_dir():
    import os
    return os.path.join(SPEASY_CONFIG_DIR, "archive")


def get_or_make_node(path: str, root: SpeasyIndex) -> SpeasyIndex:
    parts = path.split('/', maxsplit=1)
    name = parts[0]
    if name not in root.__dict__:
        root.__dict__[name] = SpeasyIndex(name=name, provider='archive', uid='')
    if len(parts) == 1:
        return root.__dict__[name]
    return get_or_make_node(parts[1], root.__dict__[name])


@CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
def _is_up(host, port) -> bool:
    return is_server_up(host=host, port=port)


def _is_reachable(url: str) -> bool:
    host, port = host_and_port(url)
    return _is_up(host, port)


def load_inventory_file(file: str, root: SpeasyIndex):
    import yaml
    with open(file, 'r') as f:
        entries = yaml.safe_load(f)
        for name, entry in entries.items():
            path = f"{entry['inventory_path']}/{name}"
            parent = get_or_make_node(entry['inventory_path'], root)
            entry_meta = {"spz_ga_cfg": entry}
            entry_meta['spz_ga_cfg']['use_file_list'] = entry_meta['spz_ga_cfg'].get('use_file_list', False)
            if is_local_file(entry['master_cdf']) or _is_reachable(entry['master_cdf']):
                dataset = make_dataset_index(entry['master_cdf'], name=name, uid=path, provider='archive',
                                             meta=entry_meta,
                                             params_uid_format=f"{path}/{{var_name}}", params_meta=entry_meta)
                if dataset:
                    parent.__dict__[dataset.spz_name()] = dataset
            else:
                log.warning(f"Master CDF {entry['master_cdf']} is not available, skipping dataset {name}")


class GenericArchive(DataProvider):
    def __init__(self):
        DataProvider.__init__(self, provider_name='archive', provider_alt_names=['generic_archive', 'file'],
                              inventory_disable_proxy=True)

    def build_inventory(self, root: SpeasyIndex):
        from glob import glob
        lookup_dirs = cfg.extra_inventory_lookup_dirs.get()
        lookup_dirs.add(_global_inventory_dir())
        lookup_dirs.add(user_inventory_dir())
        for lookup_dir in lookup_dirs:
            for file in glob(f"{lookup_dir}/*.y*ml"):
                load_inventory_file(file, root)
        return root

    def _parameter_index(self, product: str or ParameterIndex) -> ParameterIndex:
        if type(product) is str:
            if product in self.flat_inventory.parameters:
                return self.flat_inventory.parameters[product]
            else:
                raise ValueError(f"Unknown product {product}")
        elif isinstance(product, ParameterIndex):
            return product
        else:
            raise ValueError(f"Got unexpected type {type(product)}, expecting str or ParameterIndex")

    @AllowedKwargs(GET_DATA_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + ['force_refresh'])
    def get_data(self, product: str or ParameterIndex, start_time: AnyDateTimeType, stop_time: AnyDateTimeType,
                 **kwargs) -> Optional[SpeasyVariable]:
        var = self._get_data(product=self._parameter_index(product), start_time=start_time, stop_time=stop_time,
                             **kwargs)
        return var

    def _get_data(self, product: ParameterIndex, start_time: AnyDateTimeType, stop_time: AnyDateTimeType, **kwargs) -> \
    Optional[
        SpeasyVariable]:
        ga_cfg: dict = getattr(product, 'spz_ga_cfg')
        return get_product(**ga_cfg,
                           variable=product.spz_name(), start_time=start_time, stop_time=stop_time, **kwargs)
