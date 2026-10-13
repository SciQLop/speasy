"""The list of HAPI servers, from a snapshot of the official registry bundled with Speasy.

The snapshot comes from https://github.com/hapi-server/servers/blob/master/abouts.json, the file HAPI clients are
asked to use, and is refreshed at release time.
"""
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

from speasy.core import fix_name

BUNDLED_REGISTRY = Path(__file__).parents[2] / 'data' / 'hapi' / 'abouts.json'


def server_key(name: str) -> str:
    """Server keys are public names (``hapi/<key>/...``): separators become '_' instead of being dropped."""
    return fix_name(re.sub(r'\W+', '_', name).strip('_')).lower()


def bundled_registry() -> List[dict]:
    with open(BUNDLED_REGISTRY, encoding='utf-8') as f:
        return json.load(f)


def enabled_servers(registry: Iterable[Mapping], disabled: Iterable[str], extra: Mapping[str, str]) -> Dict[str, dict]:
    """Registry records by server key, plus ``extra`` ``{key: url}`` servers, minus the ``disabled`` keys."""
    servers = {server_key(entry['id']): dict(entry) for entry in registry}
    servers.update({server_key(key): {'id': key, 'title': key, 'x_url': url} for key, url in extra.items()})
    disabled_keys = {server_key(key) for key in disabled}
    return {key: record for key, record in servers.items() if key not in disabled_keys}
