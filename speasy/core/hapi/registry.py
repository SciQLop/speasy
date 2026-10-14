"""The list of HAPI servers, from a snapshot of the official registry bundled with Speasy.

The snapshot comes from https://github.com/hapi-server/servers/blob/master/abouts.json, the file HAPI clients are
asked to use, and is refreshed at release time.
"""
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional
from urllib.parse import urlparse

from speasy.core import fix_name

BUNDLED_REGISTRY = Path(__file__).parents[2] / 'data' / 'hapi' / 'abouts.json'

NATIVELY_SERVED = {
    'cdaweb.gsfc.nasa.gov': 'cda',
    'amda.irap.omp.eu': 'amda',
    'csatools.esac.esa.int': 'csa',
    'hapi-server.org/servers/sscweb': 'ssc',
}
"""``host[/path]`` prefixes of HAPI servers Speasy has a native provider for, whatever the configuration: HAPI
requests would only add load to them, and binary ones crash AMDA's."""


def native_provider(url: str) -> Optional[str]:
    parsed = urlparse(url)
    location = f"{parsed.hostname or ''}{parsed.path}".lower()
    return next((name for prefix, name in NATIVELY_SERVED.items() if location.startswith(prefix)), None)


def blocked_reason(url: str) -> Optional[str]:
    name = native_provider(url)
    if name is None:
        return None
    return (f"{url} is served natively by Speasy: use spz.{name} instead (e.g. spz.get_data('{name}/...')). Speasy "
            f"never sends HAPI requests to the servers it serves natively")


def server_key(name: str) -> str:
    """Server keys are public names (``hapi/<key>/...``): separators become '_' instead of being dropped."""
    return fix_name(re.sub(r'\W+', '_', name).strip('_')).lower()


def bundled_registry() -> List[dict]:
    with open(BUNDLED_REGISTRY, encoding='utf-8') as f:
        return json.load(f)


def enabled_servers(registry: Iterable[Mapping], disabled: Iterable[str], extra: Mapping[str, str]) -> Dict[str, dict]:
    """Registry records by server key, plus ``extra`` ``{key: url}`` servers, minus the ``disabled`` keys and the
    blocked hosts."""
    servers = {server_key(entry['id']): dict(entry) for entry in registry}
    servers.update({server_key(key): {'id': key, 'title': key, 'x_url': url} for key, url in extra.items()})
    disabled_keys = {server_key(key) for key in disabled}
    return {key: record for key, record in servers.items()
            if key not in disabled_keys and blocked_reason(record['x_url']) is None}
