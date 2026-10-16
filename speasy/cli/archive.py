import os
from glob import glob
from typing import Optional

from cyclopts import App

from ._common import console, error, table

app = App(name='archive', help="Work with the YAML archive inventories.")


@app.command
def validate(*files: str, start: Optional[str] = None, stop: Optional[str] = None) -> int:
    """Check YAML inventory files the way Speasy loads them, and show the inventory they produce.

    Exits with 1 when any file has a problem.

    Parameters
    ----------
    files: str
        YAML inventory files.
    start: Optional[str]
        Also fetch one variable per dataset from START (needs --stop).
    stop: Optional[str]
        End of that fetch (needs --start).
    """
    from speasy.data_providers.generic_archive import validate_inventory_file
    if (start is None) != (stop is None):
        return error("--start and --stop go together")
    results = [validate_inventory_file(file, start, stop) for file in files]
    return 0 if all(results) else 1


def _lookup_dirs():
    from speasy.config import archive as cfg
    from speasy.data_providers.generic_archive import user_inventory_dir, _global_inventory_dir
    return [(os.path.normpath(_global_inventory_dir()), 'bundled'), (user_inventory_dir(), 'user'),
            *((d, 'extra') for d in sorted(cfg.extra_inventory_lookup_dirs.get()))]


@app.command
def dirs() -> int:
    """List the directories Speasy scans for YAML inventory files."""
    rows = [(d, kind, 'yes' if os.path.isdir(d) else 'no', str(len(glob(f"{d}/*.y*ml"))))
            for d, kind in _lookup_dirs()]
    console().print(table('Directory', 'Kind', 'Exists', 'YAML files', rows=rows))
    console().print("Add a directory with: speasy config add archive.extra_inventory_lookup_dirs DIR")
    return 0
