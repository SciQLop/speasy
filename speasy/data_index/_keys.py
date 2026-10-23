"""The 24 h fragment grid and the keys of a data index."""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import quote

from speasy.core import AnyDateTimeType, make_utc_datetime
from speasy.core.dataprovider import provider_class

FRAGMENT = timedelta(hours=24)
_KEY_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def fragments(start: AnyDateTimeType, stop: AnyDateTimeType, now: Optional[datetime] = None) -> List[datetime]:
    """The grid fragments overlapping [start, stop), up to now: the future is never fetched."""
    start = make_utc_datetime(start)
    stop = min(make_utc_datetime(stop), now or datetime.now(tz=timezone.utc))
    first = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return [first + i * FRAGMENT for i in range(math.ceil((stop - first) / FRAGMENT))]


def runs(fragment_starts: List[datetime]) -> List[List[datetime]]:
    """Groups sorted fragment starts into runs of consecutive fragments, each fetched in one request."""
    grouped = []
    for fragment in fragment_starts:
        if grouped and grouped[-1][-1] + FRAGMENT == fragment:
            grouped[-1].append(fragment)
        else:
            grouped.append([fragment])
    return grouped


def options_hash(options: dict) -> str:
    return hashlib.sha256(json.dumps(options, sort_keys=True).encode()).hexdigest()[:16]


def _request_prefix(provider: str, product: str, options_digest: str) -> str:
    # product ids hold slashes (AC_H0_MFI/BGSEc), quoting keeps one key segment per field
    return f"{provider_class(provider).NAME}/{quote(product, safe='')}/{options_digest}"


def data_key(provider: str, product: str, options_digest: str, fragment: datetime) -> str:
    return f"data/{_request_prefix(provider, product, options_digest)}/{fragment.strftime(_KEY_TIME_FORMAT)}"


def request_key(provider: str, product: str, options_digest: str) -> str:
    return f"requests/{_request_prefix(provider, product, options_digest)}"
