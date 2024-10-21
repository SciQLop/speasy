"""
.. testsetup:: *

   from speasy.core.direct_archive_downloader.direct_archive_downloader import *
"""
import re
from datetime import timedelta, datetime
from functools import partial
import random
from typing import Optional, List, Callable

from dateutil.relativedelta import relativedelta

from speasy.core import make_utc_datetime, AnyDateTimeType
from speasy.core.cache import CacheCall
from speasy.core.any_files import list_files
from speasy.core.codecs import get_codec
from speasy.core.span_utils import intersects
from speasy.products import SpeasyVariable
from speasy.products.variable import merge

# Change to this when we drop Python 3.8
# FileLoaderCallable = Callable[[Optional[str], str, ...], Optional[SpeasyVariable]]
FileLoaderCallable = Callable[..., Optional[SpeasyVariable]]


def apply_date_format(txt: str, date: datetime) -> str:
    if date.hour // 12:
        p = 'PM'
    else:
        p = 'AM'
    return txt.format(Y=date.year, y=str(date.year)[-2:], M=date.month, D=date.day, H=date.hour,
                      j=date.timetuple().tm_yday, I=date.hour % 12,
                      p=p)


@CacheCall(cache_retention=timedelta(hours=12), is_pure=True)
def _read_cdf(url: Optional[str], variable: str, master_cdf_url: Optional[str] = None) -> Optional[SpeasyVariable]:
    if url is None:
        return None
    return get_codec('application/x-cdf').load_variable(file=url, variable=variable, master_cdf_url=master_cdf_url, cache_remote_files=True)


"""
The rationale behind the following function is to randomize the order of execution so we minimize the requests collisions and maximize the throughput.
"""
def randomized_map(f, l):
    indexed_list = list(enumerate(l))
    random.shuffle(indexed_list)
    result = sorted([(i, f(e)) for i, e in indexed_list], key=lambda x: x[0])
    return [e for i, e in result]


def _build_url(url_pattern: str, date: datetime, use_file_list=False) -> Optional[str]:
    base_ulr = apply_date_format(url_pattern, date)
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
    if split_frequency.lower() == "none":
        return [start]
    raise ValueError(f"Unknown/unimplemented split_frequency: {split_frequency}")


def _parse_date(date: str or datetime, date_format: Optional[str] = None) -> datetime:
    if isinstance(date, datetime) or date_format is None:
        return make_utc_datetime(date)
    if date_format is not None:
        return make_utc_datetime(datetime.strptime(date, date_format))


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
                   fname_regex: str, date_format=None):

        keep = []
        start_time = make_utc_datetime(start_time)
        stop_time = make_utc_datetime(stop_time)
        for start in spilt_range(split_frequency, start_time, stop_time):

            base_ulr = apply_date_format(url_pattern, start)
            folder_url, rx = base_ulr.rsplit('/', 1)
            files: List[re.Match] = list(
                filter(lambda m: m is not None, map(re.compile(fname_regex).match,
                                                    list_files(folder_url,
                                                               re.compile(rx)))))
            if len(files):
                for index, file in enumerate(files[:-1]):
                    d = file.groupdict()
                    if RandomSplitDirectDownload.overlaps_range(range_start=start_time, range_stop=stop_time,
                                                                start=_parse_date(d['start'], date_format),
                                                                stop=_parse_date(d.get('stop',
                                                                                       files[index + 1].groupdict()[
                                                                                           'start']), date_format)):
                        keep.append(f'{folder_url}/{file.string}')

                d = files[-1].groupdict()
                if RandomSplitDirectDownload.overlaps_range(range_start=start_time, range_stop=stop_time,
                                                            start=_parse_date(d['start'], date_format),
                                                            stop=_parse_date(d.get('stop', max(stop_time,
                                                                                               _parse_date(d['start'],
                                                                                                           date_format))),
                                                                             date_format)):
                    keep.append(f'{folder_url}/{files[-1].string}')
        return keep

    @staticmethod
    def get_product(url_pattern: str, variable: str, start_time: AnyDateTimeType, stop_time: AnyDateTimeType,
                    fname_regex: str, split_frequency: str = "daily", date_format=None,
                    file_reader: FileLoaderCallable = _read_cdf, **kwargs) -> Optional[SpeasyVariable]:
        v = merge(
            randomized_map(partial(file_reader, variable=variable, **kwargs),
                           RandomSplitDirectDownload.list_files(split_frequency=split_frequency,
                                                                url_pattern=url_pattern,
                                                                start_time=start_time, stop_time=stop_time,
                                                                fname_regex=fname_regex,
                                                                date_format=date_format)))
        if v is not None:
            return v[make_utc_datetime(start_time):make_utc_datetime(stop_time)]
        return None


class RegularSplitDirectDownload:

    @staticmethod
    def get_product(url_pattern: str, variable: str, start_time: AnyDateTimeType,
                    stop_time: AnyDateTimeType, use_file_list: bool = False, split_frequency: str = "daily",
                    file_reader: FileLoaderCallable = _read_cdf,
                    **kwargs) -> \
        Optional[SpeasyVariable]:
        v = merge(randomized_map(
            lambda date: file_reader(_build_url(url_pattern, date, use_file_list=use_file_list), variable=variable,
                                     **kwargs),
            spilt_range(split_frequency=split_frequency, start_time=start_time, stop_time=stop_time)))
        if v is not None:
            return v[make_utc_datetime(start_time):make_utc_datetime(stop_time)]
        return None


def get_product(url_pattern: str, split_rule: str, variable: str, start_time: AnyDateTimeType,
                stop_time: AnyDateTimeType, use_file_list: bool = False, file_reader: FileLoaderCallable = _read_cdf,
                codec: Optional[str] = None,
                **kwargs) -> Optional[SpeasyVariable]:
    if codec is not None:
        file_reader = get_codec(codec).load_variable
    if split_rule.lower() == "regular":
        return RegularSplitDirectDownload.get_product(url_pattern, variable, start_time, stop_time,
                                                      use_file_list, file_reader=file_reader, **kwargs)
    if split_rule.lower() == "random":
        return RandomSplitDirectDownload.get_product(url_pattern, variable, start_time, stop_time,
                                                     file_reader=file_reader, **kwargs)

    return None
