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
from speasy.core.cdf.inventory_extractor import make_dataset_index, extract_from_master
from speasy.core.dataprovider import DataProvider, GET_DATA_ALLOWED_KWARGS
from speasy.core.direct_archive_downloader import get_product
from speasy.core.codecs import get_codec
from speasy.core.inventory.indexes import SpeasyIndex, ParameterIndex
from speasy.core.http import is_server_up
from speasy.core.url_utils import host_and_port, is_local_file
from speasy.products.variable import SpeasyVariable
from speasy.core.cache import CacheCall, CACHE_ALLOWED_KWARGS

log = logging.getLogger(__name__)

# List of available ISTP codecs (used in _dataset_from_master() )
# The NetCDF codec is not registered if netCDF4 is not available:
# this is why we filter on None
_ISTP_CODECS = tuple(c for c in (get_codec('cdf'), get_codec('nc')) if c is not None)


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


def _public_meta(node: SpeasyIndex) -> dict:
    return {k: v for k, v in node.__dict__.items()
            if not k.startswith('__spz_') and k != 'spz_ga_cfg' and not hasattr(v, 'spz_name')}


def _merge_meta(file_meta: dict, yaml_meta: dict, priority: str) -> dict:
    # same 'meta_priority' knob resolves file-vs-YAML metadata everywhere in the pipeline:
    # here at inventory-build time (master-extracted vs YAML-declared), and again in
    # _get_data() (freshly-read file vs whatever ended up on the built ParameterIndex)
    if priority == 'yaml':
        return {**file_meta, **yaml_meta}
    return {**yaml_meta, **file_meta}


def _patch_meta(result: SpeasyVariable, inventory_meta: dict, priority: str) -> None:
    merged = _merge_meta(result.meta, inventory_meta, priority)
    result.meta.clear()
    result.meta.update(merged)


def _dataset_from_variables(name, path, entry_meta, variables, codec_id='', dataset_meta=None):
    valid = (
        dataset_meta
        and isinstance(variables, dict) and variables
        and all(isinstance(info, dict) and info.get('meta') for info in variables.values())
    )
    if not valid:
        log.warning(f"Dataset {name}: inline format requires a dataset 'meta' and a 'meta' "
                    f"for each variable, skipping")
        return None
    if get_codec(codec_id or 'cdf') is None:  # get_data() resolves this same key at fetch time
        log.warning(f"Unknown codec '{codec_id}' for dataset {name}, skipping")
        return None
    parameters = [ParameterIndex(name=var, provider='archive', uid=f"{path}/{var}",
                                 meta={**info['meta'], **entry_meta})
                  for var, info in variables.items()]
    return make_dataset_index(name=name, provider='archive', uid=path,
                              parameters=parameters,
                              meta={**dataset_meta, **entry_meta})


def _dataset_from_master(name, path, entry_meta, master_file, codec_id, dataset_meta=None, meta_priority='file'):
    # All strings for a codec id (extension, mime type, class name) resolve to the same instance in
    # the registry, so we test the codec object instead of a string
    codec = get_codec(codec_id or 'cdf')  # legacy master_cdf entries carry no codec
    if codec is None:
        log.warning(f"Unknown codec '{codec_id}' for dataset {name}, skipping")
        return None
    if codec in _ISTP_CODECS:  # ISTP formats: pyistp extraction with variable + dataset meta
        result = extract_from_master(master_file, provider='archive',
                                     params_uid_format=f"{path}/{{var_name}}",
                                     params_meta=entry_meta)
        if result:
            parameters, master_meta = result
            meta = _merge_meta(master_meta, dataset_meta or {}, meta_priority)
            return make_dataset_index(name=name, provider='archive', uid=path,
                                      parameters=parameters,
                                      meta={**meta, **entry_meta})
        return None
    variables = codec.list_variables(master_file)  # non-ISTP codecs: fall back to names only
    if variables is None:  # codec does not implement list_variables, it cannot describe a master
        log.warning(f"Codec '{codec_id}' cannot list variables for dataset {name}, skipping")
        return None
    parameters = [ParameterIndex(name=var, provider='archive', uid=f"{path}/{var}", meta=entry_meta)
                  for var in variables]
    meta = _merge_meta({}, dataset_meta or {}, meta_priority)
    return make_dataset_index(name=name, provider='archive', uid=path,
                              parameters=parameters, meta={**meta, **entry_meta})


def _load_inventory_entry(name, entry, root: SpeasyIndex):
    path = f"{entry['inventory_path']}/{name}"
    parent = get_or_make_node(entry['inventory_path'], root)
    entry_meta = {"spz_ga_cfg": entry}
    entry_meta['spz_ga_cfg']['use_file_list'] = entry_meta['spz_ga_cfg'].get('use_file_list', False)
    master_file = entry.get('master_file') or entry.get('master_cdf') or None
    if 'variables' in entry:
        dataset = _dataset_from_variables(name, path, entry_meta, entry['variables'],
                                          codec_id=entry.get('codec', ''), dataset_meta=entry.get('meta'))
    elif master_file and (is_local_file(master_file) or _is_reachable(master_file)):
        dataset = _dataset_from_master(name, path, entry_meta,
                                       master_file, entry.get('codec', ''),
                                       dataset_meta=entry.get('meta'),
                                       meta_priority=entry.get('meta_priority', 'file'))
    else:
        dataset = None
        log.warning(f"No reachable master for dataset {name}, skipping")
    if dataset:
        parent.__dict__[dataset.spz_name()] = dataset


def load_inventory_file(file: str, root: SpeasyIndex):
    import yaml
    with open(file, 'r') as f:
        entries = yaml.safe_load(f)
        for name, entry in entries.items():
            try:
                _load_inventory_entry(name, entry, root)
            except Exception:  # a malformed entry must cost only itself, not the whole provider
                log.warning(f"Dataset {name}: could not be loaded from {file}, skipping",
                            exc_info=True)


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
        ga_cfg: dict = dict(getattr(product, 'spz_ga_cfg'))  # copy: spz_ga_cfg is shared across the dataset and its params
        meta_priority = ga_cfg.pop('meta_priority', 'file')
        ga_cfg.pop('inventory_path', None)
        ga_cfg.pop('master_cdf', None)
        ga_cfg.pop('master_file', None)
        ga_cfg.pop('meta', None)
        ga_cfg.pop('variables', None)
        result = get_product(**ga_cfg,
                             variable=product.spz_name(), start_time=start_time, stop_time=stop_time, **kwargs)
        if result is not None:
            _patch_meta(result, _public_meta(product), meta_priority)
        return result
