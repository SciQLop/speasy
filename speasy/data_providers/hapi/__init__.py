"""Every server of the official HAPI registry, as ``hapi/<server>/<dataset id>/<parameter name>``.

Starting the provider contacts no server: a server's catalog is fetched on first access to its node, and each
dataset's /info on first access to the dataset, see :mod:`speasy.core.hapi.inventory`.
"""
import logging
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Iterator, List, Optional

from speasy.config import hapi as hapi_cfg
from speasy.core import AllowedKwargs, EnsureUTCDateTime
from speasy.core.cache import CACHE_ALLOWED_KWARGS, UnversionedProviderCache
from speasy.core.dataprovider import GET_DATA_ALLOWED_KWARGS, DataProvider, ParameterRangeCheck, register_provider
from speasy.core.datetime_range import DateTimeRange
from speasy.core.hapi.client import HapiClient
from speasy.core.hapi.exceptions import HapiNoData
from speasy.core.hapi.inventory import (HapiDatasetIndex, HapiServerIndex, build_inventory, fill_dataset,
                                        iso8601_duration, load_into)
from speasy.core.hapi.registry import bundled_registry, enabled_servers, server_key
from speasy.core.inventory import ProviderInventory
from speasy.core.inventory.indexes import DatasetIndex, ParameterIndex, SpeasyIndex
from speasy.core.proxy import PROXY_ALLOWED_KWARGS
from speasy.products.variable import SpeasyVariable, merge

log = logging.getLogger(__name__)

# Without maxRequestDuration, a week of 1 s cadence data is about 600k records per request.
_DEFAULT_MAX_REQUEST_DURATION = timedelta(days=7)
_NOT_HAPI_PARAMETER_META = ('start_date', 'stop_date')


def _server_records() -> Dict[str, dict]:
    return enabled_servers(bundled_registry(), hapi_cfg.disabled_servers(), hapi_cfg.extra_servers())


def _without_status(response: dict) -> dict:
    return {k: v for k, v in response.items() if k != 'status'}


def _hapi_meta(node: SpeasyIndex) -> dict:
    return {k: v for k, v in node.__dict__.items()
            if not k.startswith('__spz_') and k not in _NOT_HAPI_PARAMETER_META and not isinstance(v, SpeasyIndex)}


def _hapi_time(t: datetime) -> str:
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def _dataset_candidates(uid: str) -> Iterator[str]:
    """Dataset ids and parameter names may both contain '/': longest dataset id first."""
    parts = uid.split('/')
    return ('/'.join(parts[:i]) for i in range(len(parts), 1, -1))


@register_provider
class HapiWebservice(DataProvider):
    NAME = 'hapi'

    def __init__(self):
        self._servers = _server_records()
        self._clients: Dict[str, HapiClient] = {}
        self._flat_inventory_lock = Lock()
        HapiServerIndex.loader = self._load_server
        HapiDatasetIndex.loader = self._load_dataset
        # speasy-proxy doesn't serve a 'hapi' inventory (yet), and building ours costs no request.
        DataProvider.__init__(self, inventory_disable_proxy=True)

    def build_inventory(self, root: SpeasyIndex) -> SpeasyIndex:
        for key, record in self._servers.items():
            root.__dict__[key] = HapiServerIndex(name=key, provider=self.provider_name, uid=key,
                                                 meta={**record, 'hapi_loaded': False})
        return root

    def _load_server(self, node: HapiServerIndex) -> None:
        client = HapiClient(node.__dict__['x_url'])
        depth = 'all' if 'all' in client.capabilities.get('catalogDepthOptions', []) else None
        catalog = client.get_catalog(depth=depth)['catalog']
        server_meta = {**_without_status(client.capabilities), **self._about(client)}
        load_into(node, lambda staging: build_inventory(staging, server_meta, catalog, dataset_type=HapiDatasetIndex))
        self._clients[node.spz_uid()] = client
        self._register(node)

    def _load_dataset(self, node: HapiDatasetIndex) -> None:
        key, dataset_id = node.spz_uid().split('/', 1)
        info = self._client(key).get_info(dataset_id)
        load_into(node, lambda staging: fill_dataset(staging, info))
        self._register(node)

    @staticmethod
    def _about(client: HapiClient) -> dict:
        """/about only exists since HAPI 3.0 and only adds metadata: a broken one must not hide the server."""
        if not client.is_v3:
            return {}
        try:
            return _without_status(client.get_about())
        except Exception as e:  # pylint: disable=broad-except
            log.warning(f"Ignoring the /about of {client.base_url}: {e!r}")
            return {}

    def _register(self, node: SpeasyIndex) -> None:
        """Swaps whole dicts, so a reader iterating the flat inventory never sees it change size."""
        loaded = ProviderInventory()
        loaded.update(node)
        with self._flat_inventory_lock:
            self.flat_inventory.datasets = {**self.flat_inventory.datasets, **loaded.datasets}
            self.flat_inventory.parameters = {**self.flat_inventory.parameters, **loaded.parameters}

    def _server_node(self, key: str) -> HapiServerIndex:
        node = self._root().__dict__.get(key)
        if isinstance(node, HapiServerIndex):
            return node
        if server_key(key) in {server_key(k) for k in hapi_cfg.disabled_servers()}:
            raise ValueError(f"HAPI server {key!r} is disabled, remove it from the [HAPI] disabled_servers config "
                             f"entry (or SPEASY_HAPI_DISABLED_SERVERS) to use it")
        known = ', '.join(sorted(self._servers))
        raise ValueError(f"Unknown HAPI server {key!r}, known servers are: {known}. A server missing from the HAPI "
                         f"registry can be added with the [HAPI] extra_servers config entry, "
                         f"e.g. {{\"{key}\": \"https://example.org/hapi\"}}")

    def _root(self) -> SpeasyIndex:
        from speasy.inventories import tree
        return tree.__dict__[self.provider_name]

    def _client(self, key: str) -> HapiClient:
        if key not in self._clients:
            self._server_node(key)._load()
        return self._clients[key]

    def _resolve(self, uid: str) -> None:
        """Loads what ``uid`` needs: its server, then the dataset it belongs to."""
        self._server_node(uid.split('/', 1)[0])._load()
        for candidate in _dataset_candidates(uid):
            dataset = self.flat_inventory.datasets.get(candidate)
            if dataset is not None:
                if isinstance(dataset, HapiDatasetIndex):
                    dataset._load()
                if candidate == uid or uid in self.flat_inventory.parameters:
                    return

    def _dataset_of(self, parameter: ParameterIndex) -> DatasetIndex:
        uid = parameter.spz_uid()
        for candidate in _dataset_candidates(uid):
            dataset = self.flat_inventory.datasets.get(candidate)
            if dataset is not None and uid in dataset:
                return dataset
        raise ValueError(f"Can't find the HAPI dataset of {uid}")

    def _to_parameter_index(self, index_or_str) -> ParameterIndex:
        if type(index_or_str) is str and index_or_str not in self.flat_inventory.parameters:
            self._resolve(index_or_str)
        return super()._to_parameter_index(index_or_str)

    def _to_dataset_index(self, index_or_str) -> DatasetIndex:
        if type(index_or_str) is str and index_or_str not in self.flat_inventory.datasets:
            self._resolve(index_or_str)
        return super()._to_dataset_index(index_or_str)

    def parameter_range(self, parameter_id: str or ParameterIndex) -> Optional[DateTimeRange]:
        """Get product time range.

        Parameters
        ----------
        parameter_id: str or ParameterIndex
            parameter id, as ``<server>/<dataset id>/<parameter name>``

        Returns
        -------
        Optional[DateTimeRange]
            Data time range
        """
        return self._parameter_range(parameter_id)

    def dataset_range(self, dataset_id: str or DatasetIndex) -> Optional[DateTimeRange]:
        """Get dataset time range.

        Parameters
        ----------
        dataset_id: str or DatasetIndex
            dataset id, as ``<server>/<dataset id>``

        Returns
        -------
        Optional[DateTimeRange]
            Data time range
        """
        return self._dataset_range(dataset_id)

    @AllowedKwargs(PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + GET_DATA_ALLOWED_KWARGS)
    @EnsureUTCDateTime()
    @ParameterRangeCheck()
    def get_data(self, product: str or ParameterIndex, start_time: datetime, stop_time: datetime,
                 disable_proxy: bool = False, progress: bool = False, **kwargs) -> Optional[SpeasyVariable]:
        """Get a HAPI parameter. ``disable_proxy`` and ``progress`` are accepted for uniformity with the other
        providers: HAPI requests never use the proxy, and a single parameter has no progress to show."""
        return self._get_data(product, start_time=start_time, stop_time=stop_time, **kwargs)

    @UnversionedProviderCache(prefix="hapi", fragment_hours=lambda product: 12, cache_retention=timedelta(days=7))
    def _get_data(self, product: str, start_time: datetime, stop_time: datetime,
                  if_newer_than: Optional[datetime] = None, extra_http_headers: Optional[Dict] = None) -> \
            Optional[SpeasyVariable]:
        parameter = self._to_parameter_index(product)
        dataset = self._dataset_of(parameter)
        max_duration = iso8601_duration(dataset.__dict__.get('maxRequestDuration')) or _DEFAULT_MAX_REQUEST_DURATION
        return merge(self._download(parameter, dataset, chunk, extra_http_headers)
                     for chunk in _chunks(DateTimeRange(start_time, stop_time), max_duration))

    def _download(self, parameter: ParameterIndex, dataset: DatasetIndex, time_range: DateTimeRange,
                  extra_http_headers: Optional[Dict]) -> Optional[SpeasyVariable]:
        key, dataset_id = dataset.spz_uid().split('/', 1)
        client = self._client(key)
        header = {'HAPI': client.capabilities.get('HAPI'),
                  'parameters': [dataset.__dict__['time_parameter'], _hapi_meta(parameter)]}
        name = parameter.__dict__['name']
        try:
            return client.get_data(dataset_id, _hapi_time(time_range.start_time), _hapi_time(time_range.stop_time),
                                   [name], header=header, headers=extra_http_headers).get(name)
        except HapiNoData:
            return None


def _chunks(time_range: DateTimeRange, max_duration: timedelta) -> List[DateTimeRange]:
    return [time_range] if time_range.duration <= max_duration else time_range.split(max_duration)
