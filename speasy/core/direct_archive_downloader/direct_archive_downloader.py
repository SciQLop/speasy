"""
.. testsetup:: *

   from speasy.core.direct_archive_downloader.direct_archive_downloader import *
"""
import re
from datetime import timedelta, datetime
from functools import partial
from typing import Optional, List

from dateutil.relativedelta import relativedelta

from speasy.core import make_utc_datetime, AnyDateTimeType
from speasy.core.any_files import list_files, is_local_file
from speasy.core.cache import CacheCall
from speasy.core.cdf import load_variable
from speasy.core.span_utils import intersects
from speasy.products import SpeasyVariable
from speasy.products.variable import merge


def _read_cdf(url: Optional[str], variable: str, **kwargs) -> Optional[SpeasyVariable]:
    if url is None:
        return None
    if is_local_file(url):
        return _local_read_cdf(file=url, variable=variable, **kwargs)
    return _remote_read_cdf(url=url, variable=variable, **kwargs)


def _local_read_cdf(file: str, variable: str, **kwargs) -> Optional[SpeasyVariable]:
    return load_variable(file=file, variable=variable)


@CacheCall(cache_retention=timedelta(hours=24), is_pure=True)
def _remote_read_cdf(url: str, variable: str, **kwargs) -> Optional[SpeasyVariable]:
    return load_variable(file=url, variable=variable, cache_remote_files=False)


def _build_url(url_pattern: str, date: datetime, use_file_list=False) -> Optional[str]:
    base_ulr = url_pattern.format(Y=date.year, M=date.month, D=date.day)
    if not use_file_list:
        return base_ulr
    folder_url, rx = base_ulr.rsplit('/', 1)
    files = sorted(list_files(folder_url, re.compile(rx)))
    if len(files):
        return '/'.join((folder_url, files[-1]))
    return None


def spilt_range(split_frequency: str, start_time: AnyDateTimeType, stop_time: AnyDateTimeType):
    """Given a split frequency (daily, yearly) and a time range, generate the list of start time of each fragment given
    a split frequency (daily, yearly) and a time range to split.

    Parameters
    ----------
    split_frequency : str
        Fragments spilt frequency (daily, monthly, yearly)
    start_time : AnyDateTimeType
        Time range start
    stop_time : AnyDateTimeType
        Time range stop

    Returns
    -------
    List[datetime]
        Ordered list of start time of each fragment composing the given input range

    Examples
    --------
    >>> spilt_range('daily', "2018-01-02", "2018-01-03")
    [datetime.datetime(2018, 1, 2, 0, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2018, 1, 3, 0, 0, tzinfo=datetime.timezone.utc)]
    """
    start: datetime = make_utc_datetime(start_time)
    stop: datetime = make_utc_datetime(stop_time)
    if split_frequency.lower() == "daily":
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return [start + timedelta(days=d) for d in range((stop - start).days + 1)]
    if split_frequency.lower() == "monthly":
        start = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return [start + relativedelta(months=m) for m in range(relativedelta(stop, start).months + 1)]
    if split_frequency.lower() == "yearly":
        start = start.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return [start + relativedelta(years=y) for y in range(relativedelta(stop, start).years + 1)]
    raise ValueError(f"Unknown/unimplemented split_frequency: {split_frequency}")


class RandomSplitDirectDownload:

    @staticmethod
    def overlaps_range(range_start, range_stop, start, stop, version=None):
        start = make_utc_datetime(start)
        stop = make_utc_datetime(stop)
        if start == stop:
            return range_start <= start and range_stop >= stop
        return intersects((start, stop), (range_start, range_stop))

    @staticmethod
    def list_files(split_frequency, url_pattern: str, start_time: AnyDateTimeType, stop_time: AnyDateTimeType,
                   fname_regex: str,
                   **kwargs):

        keep = []
        start_time = make_utc_datetime(start_time)
        stop_time = make_utc_datetime(stop_time)
        for start in spilt_range(split_frequency, start_time, stop_time):
            base_ulr = url_pattern.format(Y=start.year, M=start.month, D=start.day, H=start.hour)
            folder_url, rx = base_ulr.rsplit('/', 1)
            files: List[re.Match] = list(
                filter(lambda m: m is not None, map(re.compile(fname_regex).match,
                                                    list_files(folder_url,
                                                               re.compile(rx)))))
            if len(files):
                for index, file in enumerate(files[:-1]):
                    d = file.groupdict()
                    if RandomSplitDirectDownload.overlaps_range(range_start=start_time, range_stop=stop_time,
                                                                start=d['start'],
                                                                stop=d.get('stop',
                                                                           files[index + 1].groupdict()['start'])):
                        keep.append(f'{folder_url}/{file.string}')

                d = files[-1].groupdict()
                if RandomSplitDirectDownload.overlaps_range(range_start=start_time, range_stop=stop_time,
                                                            start=d['start'],
                                                            stop=d.get('stop', max(stop_time,
                                                                                   make_utc_datetime(d['start'])))):
                    keep.append(f'{folder_url}/{files[-1].string}')
        return keep

    @staticmethod
    def get_product(url_pattern: str, variable: str, start_time: AnyDateTimeType, stop_time: AnyDateTimeType,
                    fname_regex: str, split_frequency: str = "daily", **kwargs) -> Optional[SpeasyVariable]:
        v = merge(
            list(map(partial(_read_cdf, variable=variable),
                     RandomSplitDirectDownload.list_files(split_frequency=split_frequency, url_pattern=url_pattern,
                                                          start_time=start_time, stop_time=stop_time,
                                                          fname_regex=fname_regex, **kwargs))))
        if v is not None:
            return v[make_utc_datetime(start_time):make_utc_datetime(stop_time)]
        return None


class RegularSplitDirectDownload:

    @staticmethod
    def get_product(url_pattern: str, variable: str, start_time: AnyDateTimeType,
                    stop_time: AnyDateTimeType, use_file_list: bool = False, split_frequency: str = "daily",
                    **kwargs) -> \
        Optional[SpeasyVariable]:
        v = merge(
            list(map(lambda date: _read_cdf(_build_url(url_pattern, date, use_file_list=use_file_list),
                                            variable=variable, **kwargs),
                     spilt_range(split_frequency=split_frequency, start_time=start_time,
                                 stop_time=stop_time))))
        if v is not None:
            return v[make_utc_datetime(start_time):make_utc_datetime(stop_time)]
        return None


def get_product(url_pattern: str, split_rule: str, variable: str, start_time: AnyDateTimeType,
                stop_time: AnyDateTimeType, use_file_list: bool = False, **kwargs) -> Optional[SpeasyVariable]:
    if split_rule.lower() == "regular":
        return RegularSplitDirectDownload.get_product(url_pattern, variable, start_time, stop_time,
                                                      use_file_list, **kwargs)
    if split_rule.lower() == "random":
        return RandomSplitDirectDownload.get_product(url_pattern, variable, start_time, stop_time,
                                                     **kwargs)

    return None
