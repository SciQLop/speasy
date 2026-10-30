"""A minimal client for TAP services (https://www.ivoa.net/documents/TAP/): synchronous ADQL queries, JSON results.

ESA's archives (CSA, SOAR, ...) answer the synchronous endpoint with complete results, so the asynchronous job API
is not needed, and going through speasy's own HTTP layer gives proxy support, retries and the user agent for free.
"""
import xml.etree.ElementTree as ElementTree
from typing import Any, Dict, List

from speasy.core import http


class TapError(Exception):
    pass


def query(tap_url: str, adql: str) -> List[Dict[str, Any]]:
    """Runs an ADQL query and returns one dict per row, keyed by column name."""
    response = http.get(f"{tap_url.rstrip('/')}/sync",
                        params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql})
    # a TAP error is a VOTable, sent with an HTTP error status or, by some services, with 200
    if not response.ok or not response.text.lstrip().startswith('{'):
        raise TapError(f"{tap_url} refused the query '{adql}': {_error_message(response)}")
    table = response.json()
    names = [column['name'] for column in table['metadata']]
    return [dict(zip(names, row)) for row in table['data']]


def _error_message(response) -> str:
    try:
        infos = ElementTree.fromstring(response.text).iterfind('.//{*}INFO')
        return next(info.text.strip() for info in infos if info.get('name') == 'QUERY_STATUS')
    except (ElementTree.ParseError, StopIteration, AttributeError):
        return f"HTTP {response.status_code}"
