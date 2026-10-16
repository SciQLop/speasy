"""What a YAML inventory file must look like, and the problems found when it doesn't.

Every function here is pure: it returns problem messages and leaves logging to the caller,
so the loader and validate_inventory_file() report exactly the same things.
"""
import difflib
import os
from typing import List, Tuple

REQUIRED = ('inventory_path', 'url_pattern', 'split_rule')
VARIABLE_SOURCES = ('master_file', 'master_cdf', 'variables')
CHOICES = {
    'split_rule': ('regular', 'random'),
    'split_frequency': ('daily', 'monthly', 'yearly', 'none'),
    'meta_priority': ('file', 'yaml'),
}
FETCH_KEYS = ('url_pattern', 'split_rule', 'split_frequency', 'use_file_list', 'fname_regex', 'date_format', 'codec')
KNOWN = frozenset((*REQUIRED, *VARIABLE_SOURCES, *CHOICES, *FETCH_KEYS, 'meta'))


def _yaml_error(file: str, error) -> str:
    mark = getattr(error, 'problem_mark', None)
    where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
    return f"{file} is not valid YAML{where}: {getattr(error, 'problem', None) or error}"


def read_entries(file: str) -> Tuple[dict, List[str]]:
    import yaml
    file = os.path.expanduser(file)
    if not os.path.exists(file):
        return {}, [f"{file} does not exist"]
    try:
        with open(file, 'r') as f:
            entries = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return {}, [_yaml_error(file, e)]
    if entries is None:
        return {}, [f"{file} is empty"]
    if not isinstance(entries, dict):
        return {}, [f"{file} must map dataset names to their description, got a {type(entries).__name__}"]
    return entries, []


def _missing_keys(entry: dict) -> List[str]:
    return [f"missing required key '{key}'" for key in REQUIRED if key not in entry]


def _bad_choices(entry: dict) -> List[str]:
    return [f"{key} is '{entry[key]}', expected one of: {', '.join(allowed)}"
            for key, allowed in CHOICES.items()
            if key in entry and str(entry[key]).lower() not in allowed]


def _missing_variable_source(entry: dict) -> List[str]:
    if any(entry.get(key) for key in VARIABLE_SOURCES):
        return []
    return ["needs 'master_file', 'master_cdf' or 'variables' to know which variables it holds"]


def _random_without_regex(entry: dict) -> List[str]:
    if str(entry.get('split_rule', '')).lower() == 'random' and not entry.get('fname_regex'):
        return ["split_rule 'random' needs a 'fname_regex' to read the dates from the file names"]
    return []


def _unknown_keys(entry: dict) -> List[str]:
    def hint(key):
        close = difflib.get_close_matches(key, KNOWN, n=1)
        return f"did you mean '{close[0]}'?" if close else f"known keys: {', '.join(sorted(KNOWN))}"

    return [f"unknown key '{key}' ({hint(key)})" for key in entry if key not in KNOWN]


def entry_problems(name: str, entry) -> Tuple[List[str], List[str]]:
    """Returns (errors, warnings): an error means the dataset cannot work, a warning is ignored by the loader."""
    if not isinstance(entry, dict):
        return [f"{name}: expected a mapping of fields, got {entry!r}"], []
    errors = [*_missing_keys(entry), *_bad_choices(entry), *_missing_variable_source(entry),
              *_random_without_regex(entry)]
    return [f"{name}: {e}" for e in errors], [f"{name}: {w}" for w in _unknown_keys(entry)]
