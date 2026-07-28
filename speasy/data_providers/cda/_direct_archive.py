from typing import Dict, Optional
import re

_version_regex = re.compile(r"%Q(\.\d+)*")
_date_format_regex = re.compile(r"(%[YymHjdMS])+t?(%[YymHjdMS])+")

substitutions = (
    ('%H', r'[0-2]\d'),
    ('%I', r'[01]\d'),
    ('%p', r'[AP]M'),
    ('%M', r'[0-5]\d'),
    ('%S', r'[0-5]\d')
)

substitutions_yearly = substitutions + (
    ('%Y', '{Y}'),
    ('%y', '{y:02d}'),
    ('%m', r'[01]\d'),
    ('%d', r'[0-3]\d'),
    ('%j', r'[0-3]\d\d')
)

substitutions_monthly = substitutions + (
    ('%Y', '{Y}'),
    ('%y', '{y:02d}'),
    ('%m', '{M:02d}'),
    ('%d', r'[0-3]\d'),
    ('%j', r'[0-3]\d\d')
)

substitutions_daily = substitutions + (
    ('%Y', '{Y}'),
    ('%y', '{y:02d}'),
    ('%m', '{M:02d}'),
    ('%d', '{D:02d}'),
    ('%j', '{j:03d}')
)

none_or_stop_date_substitutions = substitutions + (
    ('%Y', r'[12]\d\d\d'),
    ('%y', r'\d{2}'),
    ('%m', r'[01]\d'),
    ('%d', r'[0-3]\d'),
    ('%j', r'[0-3]\d\d')
)


# How CDAWeb spells a dataset's folder layout, mapped to the split frequency it implies, the
# placeholders that rebuild it, and the substitutions to apply to the file name inside it.
# %Y/%m/%d is kept although no dataset currently declares it, while the %j layouts below cover 78.
folder_layouts = {
    "%Y": ("yearly", "{Y}", substitutions_yearly),
    "%Y/%m": ("monthly", "{Y}/{M:02d}", substitutions_monthly),
    "%Y/%m/%d": ("daily", "{Y}/{M:02d}/{D:02d}", substitutions_daily),
    "%Y/%j": ("daily", "{Y}/{j:03d}", substitutions_daily),
    "%y/%j": ("daily", "{y:02d}/{j:03d}", substitutions_daily),
    "%Y%j": ("daily", "{Y}{j:03d}", substitutions_daily),
    "None": ("none", "", none_or_stop_date_substitutions),
}


def _build_date_format(file_naming: str) -> Optional[str]:
    date_format = _date_format_regex.search(file_naming)
    if date_format is None:
        return None
    return date_format.group()


def to_direct_archive_params(file_naming: str, subdivided_by: str, url: str) -> Optional[Dict]:
    if not file_naming.endswith('.cdf'):
        return None

    fname_regex = file_naming

    layout = folder_layouts.get(subdivided_by)
    if layout is None:
        return None
    split_frequency, subdivided_by, folder_substitutions = layout
    for old, new in folder_substitutions:
        file_naming = file_naming.replace(old, new, 1)

    for old, new in none_or_stop_date_substitutions:
        file_naming = file_naming.replace(old, new, 1)

    file_naming = _version_regex.sub(r".*", file_naming)
    url_pattern = f"{url}/{subdivided_by}{subdivided_by and '/'}{file_naming}"

    date_format = _build_date_format(fname_regex)
    if date_format is None:
        # nothing in the file name to read a start time from, so the random rule cannot describe
        # this dataset: it is a single fixed file (omni2.cdf, voyager1.cdf...) the regular rule
        # already covers. fname_regex/date_format are left out on purpose, they are random-only
        # and would be forwarded all the way down to the file reader.
        return {
            "url_pattern": url_pattern,
            "split_rule": 'regular',
            "split_frequency": split_frequency,
            "use_file_list": True,
        }

    fname_regex = _date_format_regex.sub(r"(?P<start>\\d+t?T?\\d+)", fname_regex, 1)
    fname_regex = _date_format_regex.sub(r"(?P<stop>\\d+t?T?\\d+)", fname_regex, 1)
    fname_regex = _version_regex.sub(r"(?P<version>.*)", fname_regex)

    return {
        "url_pattern": url_pattern,
        "split_rule": 'random',
        "split_frequency": split_frequency,
        "fname_regex": fname_regex,
        "use_file_list": True,
        "date_format": date_format
    }
