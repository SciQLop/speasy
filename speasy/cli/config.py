from typing import Optional

from cyclopts import App

from speasy import config
from ._common import console, table, warn_if_env_overrides

app = App(name='config', help="Show and change Speasy's configuration.")

_SECRETS = ('password',)


def _shown_value(entry: config.ConfigEntry) -> str:
    value = entry.get()
    if entry.key2 in _SECRETS:
        return '********' if value else ''
    if isinstance(value, set):
        return ', '.join(sorted(value))
    return str(value)


@app.command
def show(section: Optional[str] = None) -> int:
    """Print every config entry, its value and where that value comes from.

    Parameters
    ----------
    section: Optional[str]
        Only show this section, e.g. 'archive'.
    """
    rows = [(name, _shown_value(entry), config.entry_source(entry), entry.description.split('\n')[0])
            for name, entry in config.all_entries().items()
            if section is None or name.startswith(f"{section.lower()}.")]
    console().print(table('Entry', 'Value', 'Source', 'Description', rows=rows))
    console().print(f"Config file: {config.SPEASY_CONFIG_FILE}", highlight=False)
    return 0


@app.command(name='set')
def set_entry(name: str, value: str) -> int:
    """Set an entry in the config file, e.g. 'speasy config set proxy.enabled false'."""
    entry = config.find_entry(name)
    entry.set(value)
    warn_if_env_overrides(entry)
    return 0


@app.command
def reset(name: str) -> int:
    """Remove an entry from the config file, back to its default value."""
    entry = config.find_entry(name)
    config.remove_entry(entry)
    warn_if_env_overrides(entry)
    return 0


@app.command
def add(name: str, *values: str) -> int:
    """Add values to a list entry, e.g. a directory to archive.extra_inventory_lookup_dirs."""
    entry = config.find_entry(name)
    config.add_values(entry, values)
    warn_if_env_overrides(entry)
    return 0


@app.command
def remove(name: str, *values: str) -> int:
    """Remove values from a list entry."""
    entry = config.find_entry(name)
    config.remove_values(entry, values)
    warn_if_env_overrides(entry)
    return 0
