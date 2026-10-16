import logging
import threading
from contextlib import contextmanager
from functools import reduce
from typing import List, Optional, Tuple

from speasy.core import AnyDateTimeType
from speasy.core.direct_archive_downloader import first_file
from speasy.core.inventory.indexes import SpeasyIndex, ParameterIndex
from . import load_inventory_entry, fetch, fetch_kwargs
from ._checks import read_entries


class _MessageCollector(logging.Handler):
    """Collects the warnings emitted by this thread only: other threads may log meanwhile."""

    def __init__(self, messages: List[str]):
        super().__init__(level=logging.WARNING)
        self.messages = messages
        self.thread = threading.get_ident()

    def emit(self, record: logging.LogRecord):
        if record.thread == self.thread:
            reason = f": {record.exc_info[1]}" if record.exc_info else ""
            self.messages.append(f"{record.getMessage()}{reason}")


@contextmanager
def _collected_warnings():
    # pyistp is where non-ISTP master files get reported
    loggers = [logging.getLogger(name) for name in ('speasy', 'pyistp')]
    messages: List[str] = []
    collector = _MessageCollector(messages)
    for logger in loggers:
        logger.addHandler(collector)
    try:
        yield messages
    finally:
        for logger in loggers:
            logger.removeHandler(collector)


def _attributed(file: str, name: str, message: str) -> str:
    message = message.removeprefix(f"{file}: ")
    return message if name in message else f"{name}: {message}"


def _find_dataset(root: SpeasyIndex, name: str, entry: dict) -> Optional[SpeasyIndex]:
    parts = [*str(entry.get('inventory_path', '')).split('/'), name]
    return reduce(lambda node, part: node and node.__dict__.get(part), parts, root)


def _children(node) -> list:
    return [v for v in node.__dict__.values() if isinstance(v, SpeasyIndex)]


def _tree_lines(node, prefix: str = '') -> List[str]:
    children = _children(node)
    lines = []
    for i, child in enumerate(children):
        last = i == len(children) - 1
        lines.append(f"{prefix}{'└── ' if last else '├── '}{child.spz_name()}")
        if not isinstance(child, ParameterIndex):  # a parameter's components would only clutter the tree
            lines.extend(_tree_lines(child, prefix + ('    ' if last else '│   ')))
    return lines


def _fetch_report(dataset: SpeasyIndex, start_time, stop_time) -> Tuple[List[str], List[str]]:
    """One fetch of the dataset's first variable: proves url_pattern and the data files agree with the YAML."""
    param = next(v for v in dataset.__dict__.values() if isinstance(v, ParameterIndex))
    name = f"{dataset.spz_name()}: fetching {param.spz_name()} between {start_time} and {stop_time}"
    try:
        var = fetch(param, start_time, stop_time)
    except Exception as e:
        return [f"{name} failed ({type(e).__name__}: {e}), {_first_file_hint(param, start_time, stop_time)}"], []
    if var is None or len(var) == 0:
        return [f"{name} gave no data, {_first_file_hint(param, start_time, stop_time)}"], []
    return [], [f"{dataset.spz_name()}: fetched {param.spz_name()} ({len(var)} samples)"]


def _first_file_hint(param: ParameterIndex, start_time, stop_time) -> str:
    try:
        url = first_file(**fetch_kwargs(param), start_time=start_time, stop_time=stop_time)
    except Exception as e:
        return f"and resolving url_pattern failed too ({type(e).__name__}: {e})"
    if url is None:
        return "url_pattern matched no file in that range"
    return f"the first file url_pattern gives is {url}"


def _print_report(file: str, problems: List[str], successes: List[str], root: SpeasyIndex, fetched: bool):
    print(f"Checking {file}")
    for success in successes:
        print(f"  ✓ {success}")
    for problem in problems:
        print(f"  ✗ {problem}")
    if problems:
        print(f"{len(problems)} problem(s) found, fix them and run validate_inventory_file() again.")
        return
    print("No problem found. Inventory:")
    print('\n'.join(['archive', *_tree_lines(root)]))
    if not fetched:
        print("Data fetching was not tested: pass start_time and stop_time to try one fetch per dataset.")


def validate_inventory_file(file: str, start_time: Optional[AnyDateTimeType] = None,
                            stop_time: Optional[AnyDateTimeType] = None) -> bool:
    """Checks a YAML archive inventory file the way Speasy loads it, and prints what is wrong with it.

    Each dataset goes through the very same loader Speasy runs at startup, master file cache bypassed,
    so a file that passes here loads the same way in Speasy. Given a time range, it also fetches the
    first variable of each dataset, which checks ``url_pattern`` against the real data files.
    When no problem is found, it prints the inventory tree the file produces.

    Parameters
    ----------
    file : str
        Path to the YAML file
    start_time, stop_time : AnyDateTimeType, optional
        A time range where every dataset of the file has data

    Returns
    -------
    bool
        True when no problem was found

    Examples
    --------
    >>> from speasy.data_providers.generic_archive import validate_inventory_file
    >>> validate_inventory_file("my_datasets.yaml", "2018-06-01", "2018-06-02") # doctest: +SKIP
    """
    root = SpeasyIndex(name='archive', provider='archive', uid='')
    fetching = start_time is not None and stop_time is not None
    entries, problems = read_entries(file)
    successes = []
    for name, entry in entries.items():
        with _collected_warnings() as messages:
            load_inventory_entry(file, name, entry, root, disable_cache=True)
        problems.extend(_attributed(file, name, message) for message in messages)
        dataset = _find_dataset(root, name, entry) if isinstance(entry, dict) else None
        if dataset is not None and fetching:
            failed, fetched = _fetch_report(dataset, start_time, stop_time)
            problems.extend(failed)
            successes.extend(fetched)
    _print_report(file, problems, successes, root, fetched=fetching)
    return not problems
