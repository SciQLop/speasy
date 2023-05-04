from datetime import timedelta, datetime
from typing import Optional

from speasy.core import make_utc_datetime, AnyDateTimeType
from speasy.core.cdf import load_variable
from speasy.core.http import urlopen_with_retry
from speasy.products import SpeasyVariable
from speasy.products.variable import merge


def _read_cdf(url: str, variable: str) -> SpeasyVariable:
    with urlopen_with_retry(url) as remote_cdf:
        return load_variable(buffer=remote_cdf.read(), variable=variable)


def _split_request(split_rule: str, start_time: AnyDateTimeType, stop_time: AnyDateTimeType):
    start_time = make_utc_datetime(start_time)
    stop_time = make_utc_datetime(stop_time)
    if split_rule.lower() == "daily":
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        return [start_time + timedelta(days=d) for d in range((stop_time - start_time).days + 1)]
    raise ValueError(f"Unknown/unimplemented split_rule: {split_rule}")


def _build_url(url_pattern: str, date: datetime):
    return url_pattern.format(Y=date.year, M=date.month, D=date.day)


def get_product(url_pattern: str, split_rule: str, variable: str, start_time, stop_time) -> Optional[SpeasyVariable]:
    v = merge(list(map(lambda date: _read_cdf(_build_url(url_pattern, date), variable=variable),
                       _split_request(split_rule=split_rule, start_time=start_time, stop_time=stop_time))))
    if v is not None:
        return v[start_time:stop_time]
    return None
