import re
from datetime import timedelta, datetime
from typing import Optional

from speasy.core import make_utc_datetime, AnyDateTimeType
from speasy.core.any_files import any_loc_open, list_files
from speasy.core.cache import CacheCall
from speasy.core.cdf import load_variable
from speasy.products import SpeasyVariable
from speasy.products.variable import merge


@CacheCall(cache_retention=timedelta(hours=24), is_pure=True)
def _load_cdf(url: str) -> bytes:
    with any_loc_open(url) as remote_cdf:
        return remote_cdf.read()


@CacheCall(cache_retention=timedelta(hours=24), is_pure=True)
def _read_cdf(url: str, variable: str) -> SpeasyVariable:
    return load_variable(buffer=_load_cdf(url), variable=variable)


def _split_request(split_rule: str, start_time: AnyDateTimeType, stop_time: AnyDateTimeType):
    start_time = make_utc_datetime(start_time)
    stop_time = make_utc_datetime(stop_time)
    if split_rule.lower() == "daily":
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        return [start_time + timedelta(days=d) for d in range((stop_time - start_time).days + 1)]
    raise ValueError(f"Unknown/unimplemented split_rule: {split_rule}")


def _build_url(url_pattern: str, date: datetime, use_file_list=False) -> str:
    base_ulr = url_pattern.format(Y=date.year, M=date.month, D=date.day)
    if not use_file_list:
        return base_ulr
    folder_url, rx = base_ulr.rsplit('/', 1)
    return '/'.join((folder_url, sorted(list_files(folder_url, re.compile(rx)))[-1]))


def get_product(url_pattern: str, split_rule: str, variable: str, start_time: AnyDateTimeType,
                stop_time: AnyDateTimeType, use_file_list: bool = False) -> Optional[SpeasyVariable]:
    v = merge(
        list(map(lambda date: _read_cdf(_build_url(url_pattern, date, use_file_list=use_file_list), variable=variable),
                 _split_request(split_rule=split_rule, start_time=start_time, stop_time=stop_time))))
    if v is not None:
        return v[make_utc_datetime(start_time):make_utc_datetime(stop_time)]
    return None
