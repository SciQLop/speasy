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


def _build_date_format(file_naming: str) -> Optional[str]:
    date_format = _date_format_regex.search(file_naming)
    if date_format is None:
        return None
    return date_format.group()


def to_direct_archive_params(file_naming: str, subdivided_by: str, url: str) -> Optional[Dict]:
    if not file_naming.endswith('.cdf'):
        return None

    fname_regex = file_naming

    if subdivided_by == "%Y":
        split_frequency = "yearly"
        subdivided_by = "{Y}"
        for old, new in substitutions_yearly:
            file_naming = file_naming.replace(old, new, 1)
    elif subdivided_by == "%Y/%m":
        split_frequency = "monthly"
        subdivided_by = "{Y}/{M:02d}"
        for old, new in substitutions_monthly:
            file_naming = file_naming.replace(old, new, 1)
    elif subdivided_by == "%Y/%m/%d":
        split_frequency = "daily"
        subdivided_by = "{Y}/{M:02d}/{D:02d}"
        for old, new in substitutions_daily:
            file_naming = file_naming.replace(old, new, 1)
    elif subdivided_by == "None":
        split_frequency = "none"
        subdivided_by = ""
        for old, new in none_or_stop_date_substitutions:
            file_naming = file_naming.replace(old, new, 1)
    else:
        return None

    for old, new in none_or_stop_date_substitutions:
        file_naming = file_naming.replace(old, new, 1)

    file_naming = _version_regex.sub(r".*", file_naming)

    date_format = _build_date_format(fname_regex)
    fname_regex = _date_format_regex.sub(r"(?P<start>\\d+t?T?\\d+)", fname_regex, 1)
    fname_regex = _date_format_regex.sub(r"(?P<stop>\\d+t?T?\\d+)", fname_regex, 1)
    fname_regex = _version_regex.sub(r"(?P<version>.*)", fname_regex)

    return {
        "url_pattern": f"{url}/{subdivided_by}{subdivided_by and '/'}{file_naming}",
        "split_rule": 'random',
        "split_frequency": split_frequency,
        "fname_regex": fname_regex,
        "use_file_list": True,
        "date_format": date_format
    }
