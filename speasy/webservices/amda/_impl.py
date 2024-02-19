import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Dict, Optional

from . import rest_client
from .exceptions import MissingCredentials
from .inventory import AmdaXMLParser
from .rest_client import auth_args
from .utils import load_catalog, load_csv, load_timetable
# General modules
from ...config import amda as amda_cfg
from ...core.any_files import any_loc_open
from ...core.cache import CacheCall
from ...core.cdf import load_variable as cdf_load_variable
from ...core.inventory.indexes import SpeasyIndex
from ...inventories import flat_inventories
from ...products.variable import SpeasyVariable, merge

log = logging.getLogger(__name__)


def credential_are_valid():
    login = amda_cfg.username()
    password = amda_cfg.password()
    return login != "" and password != ""


def _get_credentials():
    if credential_are_valid():
        return amda_cfg.username(), amda_cfg.password()
    else:
        raise MissingCredentials()


def is_public(node):
    return node.__dict__.get('is_public', 'True') == 'True'


def is_private(node):
    return not is_public(node)


class AmdaImpl:
    def __init__(self, server_url: str = amda_cfg.entry_point()):
        self.server_url = server_url

    def _update_private_lists(self, TimeTables: SpeasyIndex, Catalogs: SpeasyIndex, root: SpeasyIndex):
        if credential_are_valid():
            username, password = _get_credentials()
            user_tt = AmdaXMLParser.parse(
                rest_client.get_user_timetables_xml_tree(username=username, password=password,
                                                         server_url=self.server_url),
                is_public=False)
            TimeTables.MyTimeTables = SpeasyIndex(name='MyTimeTables', provider='amda', uid='MyTimeTables',
                                                  meta=user_tt.timetabList.__dict__)

            user_cat = AmdaXMLParser.parse(
                rest_client.get_user_catalogs_xml_tree(username=username, password=password,
                                                       server_url=self.server_url),
                is_public=False)
            Catalogs.MyCatalogs = SpeasyIndex(name='MyCatalogs', provider='amda', uid='MyCatalogs',
                                              meta=user_cat.catalogList.__dict__)

            user_param = AmdaXMLParser.parse(
                rest_client.get_user_parameters_xml_tree(username=username, password=password,
                                                         server_url=self.server_url),
                is_public=False)
            root.DerivedParameters = SpeasyIndex(name='DerivedParameters', provider='amda', uid='DerivedParameters',
                                                 meta=user_param.ws.paramList.__dict__)

    def _update_lists(self, TimeTables: SpeasyIndex, Catalogs: SpeasyIndex, root: SpeasyIndex):

        public_tt = AmdaXMLParser.parse(rest_client.get_timetables_xml_tree(server_url=self.server_url))
        TimeTables.SharedTimeTables = SpeasyIndex(name='SharedTimeTables', provider='amda', uid='SharedTimeTables',
                                                  meta=public_tt.timeTableList.__dict__)
        public_cat = AmdaXMLParser.parse(rest_client.get_catalogs_xml_tree(server_url=self.server_url))
        Catalogs.SharedCatalogs = SpeasyIndex(name='SharedCatalogs', provider='amda', uid='SharedCatalogs',
                                              meta=public_cat.catalogList.__dict__)

    @staticmethod
    def is_server_up(server_url: str = amda_cfg.entry_point()):
        return rest_client.is_server_up(server_url=server_url)

    def build_inventory(self, root: SpeasyIndex):
        data = AmdaXMLParser.parse(rest_client.get_obs_data_tree(server_url=self.server_url))
        root.Parameters = SpeasyIndex(name='Parameters', provider='amda', uid='Parameters',
                                      meta=data.dataRoot.AMDA.__dict__)

        root.TimeTables = SpeasyIndex(name='TimeTables', provider='amda', uid='TimeTables')
        root.Catalogs = SpeasyIndex(name='Catalogs', provider='amda', uid='Catalogs')
        root.DerivedParameters = SpeasyIndex(name='DerivedParameters', provider='amda', uid='DerivedParameters')
        self._update_lists(TimeTables=root.TimeTables, Catalogs=root.Catalogs, root=root)
        return root

    def build_private_inventory(self, root: SpeasyIndex):
        self._update_private_lists(TimeTables=root.TimeTables, Catalogs=root.Catalogs, root=root)
        return root

    def dl_parameter_chunk(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                           extra_http_headers: Dict or None = None, output_format: str = 'ASCII', **kwargs) -> Optional[
        SpeasyVariable]:
        url = rest_client.get_parameter(server_url=self.server_url, startTime=start_time.timestamp(),
                                        stopTime=stop_time.timestamp(), parameterID=parameter_id, timeFormat='UNIXTIME',
                                        extra_http_headers=extra_http_headers, outputFormat=output_format, **kwargs)
        # check status until done
        if url is not None:
            if output_format == "CDF_ISTP":
                if url is not None:
                    var = cdf_load_variable(variable=parameter_id, file=url)
            else:
                var = load_csv(url, parameter_id)
            if var is not None:
                if len(var):
                    log.debug(
                        f'Loaded var: data shape = {var.values.shape}, data start time = {var.time[0]}, \
                                data stop time = {var.time[-1]}')
                else:
                    log.debug('Loaded var: Empty var')
            else:
                log.debug(f'Failed to load file f{url}')
            return var
        return None

    def dl_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                     extra_http_headers: Dict or None = None, output_format: str = 'ASCII', restricted_period=False,
                     **kwargs) -> Optional[
        SpeasyVariable]:
        dt = timedelta(days=amda_cfg.max_chunk_size_days())
        if restricted_period:
            try:
                username, password = _get_credentials()
                kwargs['userID'] = username
                kwargs['password'] = password
            except MissingCredentials:
                raise MissingCredentials(
                    "Restricted period requested but no credentials provided, please add your AMDA credentials.")
        if stop_time - start_time > dt:
            var = None
            curr_t = start_time
            while curr_t < stop_time:
                var = merge([var, self.dl_parameter_chunk(curr_t, min(curr_t + dt, stop_time), parameter_id,
                                                          extra_http_headers=extra_http_headers,
                                                          output_format=output_format, **kwargs)])
                curr_t += dt
            return var
        else:
            return self.dl_parameter_chunk(start_time, stop_time, parameter_id, extra_http_headers=extra_http_headers,
                                           output_format=output_format, **kwargs)

    def dl_user_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str,
                          **kwargs) -> Optional[SpeasyVariable]:
        username, password = _get_credentials()
        return self.dl_parameter(parameter_id=parameter_id, start_time=start_time, stop_time=stop_time,
                                 **auth_args(username=username, password=password), **kwargs)

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
    def dl_timetable(self, timetable_id: str, **kwargs):
        url = rest_client.get_timetable(ttID=timetable_id, server_url=self.server_url, **kwargs)
        if url is not None:
            timetable = load_timetable(filename=url)
            if timetable:
                timetable.meta.update(flat_inventories.amda.timetables.get(timetable_id, SimpleNamespace()).__dict__)
                log.debug(f'Loaded timetable: id = {timetable_id}')  # lgtm[py/clear-text-logging-sensitive-data]
            else:
                log.debug('Got None')
            return timetable
        return None

    def dl_user_timetable(self, timetable_id: str, **kwargs):
        username, password = _get_credentials()
        return self.dl_timetable(timetable_id, **auth_args(username=username, password=password), **kwargs)

    @CacheCall(cache_retention=amda_cfg.user_cache_retention())
    def dl_catalog(self, catalog_id: str, **kwargs):
        url = rest_client.get_catalog(catID=catalog_id, server_url=self.server_url, **kwargs)
        if url is not None:
            catalog = load_catalog(url)
            if catalog:
                log.debug(f'Loaded catalog: id = {catalog_id}')  # lgtm[py/clear-text-logging-sensitive-data]
                catalog.meta.update(flat_inventories.amda.catalogs.get(catalog_id, SimpleNamespace()).__dict__)
            else:
                log.debug('Got None')
            return catalog
        return None

    def dl_user_catalog(self, catalog_id: str, **kwargs):
        username, password = _get_credentials()
        return self.dl_catalog(catalog_id, **auth_args(username=username, password=password), **kwargs)
