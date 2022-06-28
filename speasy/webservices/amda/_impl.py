from types import SimpleNamespace

from . import rest_client
from .utils import load_csv, load_timetable, load_catalog
from .inventory import AmdaXMLParser
from .rest_client import auth_args
from .exceptions import MissingCredentials

from datetime import datetime, timedelta
from typing import Optional

# General modules
from ...config import amda_password, amda_username, amda_user_cache_retention, amda_max_chunk_size_days
from ...products.variable import SpeasyVariable, merge
from ...inventory import data_tree, flat_inventories
from ...inventory import reset_amda_inventory as reset_amda_flat_inventory
from ...core.cache import CacheCall
import logging

log = logging.getLogger(__name__)


def credential_are_valid():
    login = amda_username.get()
    password = amda_password.get()
    return login != "" and password != ""


def _get_credentials():
    if credential_are_valid():
        return amda_username.get(), amda_password.get()
    else:
        raise MissingCredentials()


def is_public(node):
    return node.__dict__.get('is_public', True)


def is_private(node):
    return not is_public(node)


class AmdaImpl:
    def __init__(self, server_url: str = "http://amda.irap.omp.eu"):
        self.server_url = server_url
        self.update_inventory()

    def _update_lists(self):
        if credential_are_valid():
            username, password = _get_credentials()
            user_tt = AmdaXMLParser.parse(
                rest_client.get_user_timetables_xml_tree(username=username, password=password,
                                                         server_url=self.server_url),
                is_public=False)
            data_tree.amda.TimeTables.MyTimeTables.__dict__.update(user_tt.timetabList.__dict__)

            user_cat = AmdaXMLParser.parse(
                rest_client.get_user_catalogs_xml_tree(username=username, password=password,
                                                       server_url=self.server_url),
                is_public=False)
            data_tree.amda.Catalogs.MyCatalogs.__dict__.update(user_cat.catalogList.__dict__)

            user_param = AmdaXMLParser.parse(
                rest_client.get_user_parameters_xml_tree(username=username, password=password,
                                                         server_url=self.server_url),
                is_public=False)
            data_tree.amda.DerivedParameters.__dict__.update(user_param.ws.paramList.__dict__)

        public_tt = AmdaXMLParser.parse(rest_client.get_timetables_xml_tree(server_url=self.server_url))
        data_tree.amda.TimeTables.SharedTimeTables.__dict__.update(public_tt.timeTableList.__dict__)
        public_cat = AmdaXMLParser.parse(rest_client.get_catalogs_xml_tree(server_url=self.server_url))
        data_tree.amda.Catalogs.SharedCatalogs.__dict__.update(public_cat.catalogList.__dict__)

    @staticmethod
    def _clear_inventory():
        data_tree.reset_amda_inventory()
        reset_amda_flat_inventory()

    def update_inventory(self):
        """Load AMDA_Webservice invertory and save to cache.
        """
        data = AmdaXMLParser.parse(rest_client.get_obs_data_tree(server_url=self.server_url))
        data_tree.amda.Parameters.__dict__.update(data.dataRoot.AMDA.__dict__)

        self._update_lists()

    def dl_parameter_chunk(self, start_time: datetime, stop_time: datetime, parameter_id: str, **kwargs) -> Optional[
        SpeasyVariable]:
        url = rest_client.get_parameter(
            startTime=start_time.timestamp(), stopTime=stop_time.timestamp(), parameterID=parameter_id,
            timeFormat='UNIXTIME',
            server_url=self.server_url, **kwargs)
        # check status until done
        if url is not None:
            var = load_csv(url)
            if len(var):
                log.debug(
                    f'Loaded var: data shape = {var.values.shape}, data start time = {datetime.utcfromtimestamp(var.time[0])}, data stop time = {datetime.utcfromtimestamp(var.time[-1])}')
            else:
                log.debug('Loaded var: Empty var')
            return var
        return None

    def dl_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str, **kwargs) -> Optional[
        SpeasyVariable]:
        dt = timedelta(days=int(amda_max_chunk_size_days.get()))

        if stop_time - start_time > dt:
            var = None
            curr_t = start_time
            while curr_t < stop_time:
                if curr_t + dt < stop_time:
                    var = merge([var, self.dl_parameter_chunk(curr_t, curr_t + dt, parameter_id, **kwargs)])
                else:
                    var = merge([var, self.dl_parameter_chunk(curr_t, stop_time, parameter_id, **kwargs)])
                curr_t += dt
            return var
        else:
            return self.dl_parameter_chunk(start_time, stop_time, parameter_id, **kwargs)

    def dl_user_parameter(self, start_time: datetime, stop_time: datetime, parameter_id: str, **kwargs) -> Optional[
        SpeasyVariable]:
        username, password = _get_credentials()
        return self.dl_parameter(parameter_id=parameter_id, start_time=start_time, stop_time=stop_time,
                                 **auth_args(username=username, password=password), **kwargs)

    @CacheCall(cache_retention=float(amda_user_cache_retention.get()))
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

    @CacheCall(cache_retention=float(amda_user_cache_retention.get()))
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
