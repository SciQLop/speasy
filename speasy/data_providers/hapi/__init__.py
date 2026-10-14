"""Every server of the official HAPI registry, as ``hapi/<server>/<dataset id>/<parameter name>``.

Starting the provider contacts no server: a server's catalog is fetched on first access to its node, and each
dataset's /info on first access to the dataset, see :mod:`speasy.core.hapi.inventory`.
"""
import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, Iterator, List, Optional

from speasy.config import hapi as hapi_cfg
from speasy.core import AllowedKwargs, EnsureUTCDateTime
from speasy.core.cache import CACHE_ALLOWED_KWARGS, UnversionedProviderCache
from speasy.core.dataprovider import GET_DATA_ALLOWED_KWARGS, DataProvider, ParameterRangeCheck, register_provider
from speasy.core.datetime_range import DateTimeRange
from speasy.core.hapi.client import HapiClient
from speasy.core.hapi.exceptions import HapiNoData, HapiRequestError, HapiServerError, HapiServerUnavailable
from speasy.core.hapi.inventory import (HapiDatasetIndex, HapiServerIndex, build_inventory, fill_dataset,
                                        iso8601_duration, load_into)
from speasy.core.hapi.registry import blocked_reason, bundled_registry, enabled_servers, server_key
from speasy.core.inventory import ProviderInventory
from speasy.core.inventory.indexes import DatasetIndex, ParameterIndex, SpeasyIndex
from speasy.core.proxy import PROXY_ALLOWED_KWARGS
from speasy.products.variable import SpeasyVariable, merge

log = logging.getLogger(__name__)

# Without maxRequestDuration, a week of 1 s cadence data is about 600k records per request.
_DEFAULT_MAX_REQUEST_DURATION = timedelta(days=7)
_NOT_HAPI_PARAMETER_META = ('dataset', 'start_date', 'stop_date')


def _tree() -> SpeasyIndex:
    from speasy.inventories import tree  # speasy.inventories imports the providers
    return tree


def _server_records() -> Dict[str, dict]:
    return enabled_servers(bundled_registry(), hapi_cfg.disabled_servers(), hapi_cfg.extra_servers())


def _blocked_server_reason(key: str) -> Optional[str]:
    urls = {**{server_key(e['id']): e['x_url'] for e in bundled_registry()},
            **{server_key(k): url for k, url in hapi_cfg.extra_servers().items()}}
    return blocked_reason(urls.get(server_key(key), ''))


def _without_status(response: dict) -> dict:
    return {k: v for k, v in response.items() if k != 'status'}


def _hapi_meta(node: SpeasyIndex) -> dict:
    return {k: v for k, v in node.__dict__.items()
            if not k.startswith('__spz_') and k not in _NOT_HAPI_PARAMETER_META and not isinstance(v, SpeasyIndex)}


def _hapi_time(t: datetime) -> str:
    """Whole seconds when possible: a truncated fraction could start before the dataset, which servers reject."""
    return t.strftime('%Y-%m-%dT%H:%M:%S') + (f".{t.microsecond:06d}" if t.microsecond else '') + 'Z'


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

    def update_inventory(self) -> None:
        """Starts over from unloaded servers. Swapped under the lock loads publish with, so a load in flight can't
        mix nodes of the old and new trees, and readers never see a half-cleared flat inventory."""
        root = self.build_inventory(SpeasyIndex(name=self.provider_name, provider=self.provider_name,
                                                uid=self.provider_name,
                                                meta={'build_date': datetime.now(tz=timezone.utc).isoformat()}))
        with self._flat_inventory_lock:
            _tree().__dict__[self.provider_name] = root
            self.flat_inventory.datasets, self.flat_inventory.parameters = {}, {}

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
        self._clients[node.spz_uid()] = client

        def fill(staging):
            build_inventory(staging, server_meta, catalog, dataset_type=HapiDatasetIndex)
            self._publish(node, staging)
        load_into(node, fill)

    def _load_dataset(self, node: HapiDatasetIndex) -> None:
        key, dataset_id = node.spz_uid().split('/', 1)
        info = self._client(key).get_info(dataset_id)

        def fill(staging):
            fill_dataset(staging, info)
            self._publish(node, staging)
        load_into(node, fill)

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

    def _publish(self, node: SpeasyIndex, staging: SpeasyIndex) -> None:
        """Registers ``staging``'s children before ``load_into`` marks ``node`` loaded, so whoever sees it loaded
        finds its products. Nodes of a tree replaced by update_inventory() aren't registered: they still browse, but
        get_data only goes through the current tree."""
        loaded = ProviderInventory()
        loaded.update(staging)
        with self._flat_inventory_lock:
            if self._is_current(node):
                self._register(loaded)

    def _register(self, loaded: ProviderInventory) -> None:
        """Swaps whole dicts, so a reader iterating the flat inventory never sees it change size."""
        self.flat_inventory.datasets = {**self.flat_inventory.datasets, **loaded.datasets}
        self.flat_inventory.parameters = {**self.flat_inventory.parameters, **loaded.parameters}

    def _is_current(self, node: SpeasyIndex) -> bool:
        if isinstance(node, HapiServerIndex):
            return self._root().__dict__.get(node.spz_uid()) is node
        return self.flat_inventory.datasets.get(node.spz_uid()) is node

    def _server_node(self, key: str) -> HapiServerIndex:
        node = self._root().__dict__.get(key)
        if isinstance(node, HapiServerIndex):
            return node
        if (reason := _blocked_server_reason(key)) is not None:
            raise ValueError(reason)
        if server_key(key) in {server_key(k) for k in hapi_cfg.disabled_servers()}:
            raise ValueError(f"HAPI server {key!r} is disabled, remove it from the [HAPI] disabled_servers config "
                             f"entry (or SPEASY_HAPI_DISABLED_SERVERS) to use it")
        known = ', '.join(sorted(self._servers))
        raise ValueError(f"Unknown HAPI server {key!r}, known servers are: {known}. A server missing from the HAPI "
                         f"registry can be added with the [HAPI] extra_servers config entry, "
                         f"e.g. {{\"{key}\": \"https://example.org/hapi\"}}")

    def _root(self) -> SpeasyIndex:
        return _tree().__dict__[self.provider_name]

    def _client(self, key: str) -> HapiClient:
        if key not in self._clients:
            self._server_node(key)._load()
        return self._clients[key]

    def _resolve(self, uid: str) -> None:
        """Loads what ``uid`` needs: its server, then the dataset it belongs to."""
        key = uid.split('/', 1)[0]
        server = self._server_node(key)
        _load_or_explain(server, key)
        for candidate in _dataset_candidates(uid):
            dataset = self.flat_inventory.datasets.get(candidate)
            if dataset is not None:
                if isinstance(dataset, HapiDatasetIndex):
                    _load_or_explain(dataset, key)
                if candidate == uid or uid in self.flat_inventory.parameters:
                    return

    def _find(self, uid: str, kind: str) -> Optional[SpeasyIndex]:
        """``kind`` is 'datasets' or 'parameters'. update_inventory() empties the flat inventory: a lookup it
        interleaves with starts over on the new tree, rather than reporting a valid product as unknown."""
        while True:
            root = self._root()
            if uid not in getattr(self.flat_inventory, kind):
                self._resolve(uid)
            found = getattr(self.flat_inventory, kind).get(uid)
            if found is not None or self._root() is root:
                return found

    def _dataset_of(self, parameter: ParameterIndex) -> DatasetIndex:
        uid = parameter.__dict__['dataset']
        dataset = self._find(uid, 'datasets')
        if dataset is None:
            raise ValueError(f"HAPI dataset {uid!r} is no longer listed by its server, "
                             f"browse spz.inventories.tree.hapi.{uid.split('/', 1)[0]} to see what it offers now")
        return dataset

    def _to_parameter_index(self, index_or_str) -> ParameterIndex:
        if type(index_or_str) is not str:
            return super()._to_parameter_index(index_or_str)
        parameter = self._find(index_or_str, 'parameters')
        if parameter is not None:
            return parameter
        if self._find(index_or_str, 'datasets') is not None:
            raise ValueError(f"{index_or_str!r} is a HAPI dataset, get its parameters one by one: "
                             f"spz.inventories.tree.hapi.{index_or_str.split('/', 1)[0]} lists them")
        raise ValueError(f"Unknown HAPI product {index_or_str!r}, browse "
                         f"spz.inventories.tree.hapi.{index_or_str.split('/', 1)[0]} to see the datasets and "
                         f"parameters it offers")

    def _to_dataset_index(self, index_or_str) -> DatasetIndex:
        if type(index_or_str) is not str:
            return super()._to_dataset_index(index_or_str)
        dataset = self._find(index_or_str, 'datasets')
        if dataset is None:
            raise ValueError(f"Unknown HAPI dataset {index_or_str!r}, browse "
                             f"spz.inventories.tree.hapi.{index_or_str.split('/', 1)[0]} to see the datasets it offers")
        return dataset

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
        time_range = _clamped(DateTimeRange(start_time, stop_time), self._dataset_range(dataset))
        if time_range is None:
            return None
        max_duration = iso8601_duration(dataset.__dict__.get('maxRequestDuration')) or _DEFAULT_MAX_REQUEST_DURATION
        return merge(self._download(parameter, dataset, chunk, extra_http_headers)
                     for chunk in _chunks(time_range, max_duration))

    def _download(self, parameter: ParameterIndex, dataset: DatasetIndex, time_range: DateTimeRange,
                  extra_http_headers: Optional[Dict]) -> Optional[SpeasyVariable]:
        key, dataset_id = dataset.spz_uid().split('/', 1)
        client = self._client(key)
        header = {'HAPI': client.capabilities.get('HAPI'),
                  'parameters': [dataset.__dict__['time_parameter'], _hapi_meta(parameter)]}
        name = parameter.__dict__['name']
        start, stop = _hapi_time(time_range.start_time), _hapi_time(time_range.stop_time)
        try:
            return client.get_data(dataset_id, start, stop, [name], header=header, headers=extra_http_headers).get(name)
        except HapiNoData:
            return None
        except (HapiRequestError, HapiServerError) as e:
            raise type(e)(e.code, f"{e.message} (getting {name!r} of {dataset_id!r} from {start} to {stop} "
                                  f"on {client.base_url})") from e


def _load_or_explain(node, key: str) -> None:
    try:
        node._load()
    except Exception as e:
        raise HapiServerUnavailable(
            f"HAPI server {key!r} is unreachable or misbehaving, loading {node.spz_uid()!r} failed with {e!r}. "
            f"Try again later, or stop listing this server with the [HAPI] disabled_servers config entry "
            f"(or SPEASY_HAPI_DISABLED_SERVERS)") from e


def _clamped(time_range: DateTimeRange, dataset_range: DateTimeRange) -> Optional[DateTimeRange]:
    """The cache asks for whole fragments, which can overflow the dataset: servers answer 1405 to that."""
    start, stop = max(time_range.start_time, dataset_range.start_time), min(time_range.stop_time, dataset_range.stop_time)
    return DateTimeRange(start, stop) if start < stop else None


def _chunks(time_range: DateTimeRange, max_duration: timedelta) -> List[DateTimeRange]:
    return [time_range] if time_range.duration <= max_duration else time_range.split(max_duration)
