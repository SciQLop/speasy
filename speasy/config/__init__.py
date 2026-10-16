"""
speasy.config
-------------

Configuration module for SPEASY, it reads or sets config entries first from ENV then from config file.
"""

import configparser
import os
from typing import Any, Dict, Iterable
import ast
import difflib

import appdirs

from ..core import mkdir

SPEASY_CONFIG_DIR = str(appdirs.user_config_dir(appname="speasy", appauthor="LPP"))

SPEASY_CONFIG_FILE = os.path.join(SPEASY_CONFIG_DIR, "config.ini")
mkdir(os.path.dirname(SPEASY_CONFIG_FILE))
_config = configparser.ConfigParser()
_config.read(SPEASY_CONFIG_FILE)

_entries = {}


def _parse_dir_set(value: str) -> set:
    """Comma-separated directory list -> set, dropping empty entries and the literal
    string 'set()' -- installs that ran before user_codecs_extra_dirs/extra_inventory_lookup_dirs
    got an empty-string default may already have str(set()) persisted to their config.ini/env."""
    return {p for p in value.split(',') if p and p != 'set()'}


def _load_dict_from_repr(value: str):
    if value:
        d = ast.literal_eval(value)
        if isinstance(d, dict):
            return d
        else:
            raise ValueError(f"Config value can't be converted to dict: {value}")
    return {}


def show():
    """Prints config entries and current values
    """
    for section in _entries.values():
        print(section)


def _save_changes():
    with open(SPEASY_CONFIG_FILE, 'w') as f:
        _config.write(f)


class ConfigEntry:
    """Configuration entry class. Used to set and get configuration values.

    Attributes
    ----------
    key1: str
        Module or category name
    key2: str
        Entry name
    default: str
        Default value
    type_ctor: Any
        function called to get value from string repr
    env_var_name: str
        Environment variable name to use to set this entry

    Methods
    -------
    get:
        Get entry current value
    set:
        Set entry value (could be env or file)
    """

    def __init__(self, key1: str, key2: str, default: Any = "", type_ctor=None, description: str = ""):
        self.key1 = key1
        self.key2 = key2
        self.default = str(default)
        self.type_ctor = type_ctor or (lambda x: x)
        self.description = description
        self.env_var_name = f"SPEASY_{self.key1}_{self.key2}".upper().replace(
            '-', '_')

    def __repr__(self):
        return f"""ConfigEntry: {self.key1}/{self.key2}
    environment variable name: {self.env_var_name}
    value:                     {self.get()}
    description:               {self.description}"""

    def get(self):
        """Get configuration entry value. If a default is not provided then raise :class:`~speasy.config.exceptions.UndefinedConfigEntry`.

        Returns
        -------
        str:
            configuration value
        """
        if self.env_var_name in os.environ:
            return self.type_ctor(os.environ[self.env_var_name])
        if self.key1 in _config and self.key2 in _config[self.key1]:
            return self.type_ctor(_config[self.key1][self.key2])
        return self.type_ctor(self.default)

    def set(self, value: str):
        if self.env_var_name in os.environ:
            os.environ[self.env_var_name] = str(value)
        if self.key1 not in _config:
            _config.add_section(self.key1)
        _config[self.key1][self.key2] = str(value)
        _save_changes()

    def __call__(self, *args, **kwargs):
        return self.get()


class ConfigSection:
    def __init__(self, name, **kwargs):
        self.__dict__.update({
            entry_name: ConfigEntry(name, entry_name, **e_kwargs) for entry_name, e_kwargs in kwargs.items()
        })
        _entries[name] = self
        self.name = name

    def __repr__(self):
        s = f"""
============================================
\t\t{self.name}
============================================"""
        for _, entry in self.__dict__.items():
            s += f"\n  {entry}\n-------------------------------------------"
        return s


def all_entries() -> Dict[str, ConfigEntry]:
    """Every config entry, keyed by its 'section.key' name, e.g. 'proxy.url'."""
    return {f"{section.name.lower()}.{key}": entry
            for section in _entries.values()
            for key, entry in vars(section).items() if isinstance(entry, ConfigEntry)}


def find_entry(name: str) -> ConfigEntry:
    """The entry called 'section.key' (any case), with a suggestion when there is no such entry."""
    known = all_entries()
    if name.lower() in known:
        return known[name.lower()]
    close = difflib.get_close_matches(name.lower(), known, n=1)
    hint = f"did you mean {close[0]}?" if close else "run 'speasy config show' to list them"
    raise ValueError(f"unknown config entry '{name}', {hint}")


def entry_source(entry: ConfigEntry) -> str:
    """Where the current value comes from: 'env', 'file' or 'default'."""
    if entry.env_var_name in os.environ:
        return 'env'
    if entry.key1 in _config and entry.key2 in _config[entry.key1]:
        return 'file'
    return 'default'


def is_list_entry(entry: ConfigEntry) -> bool:
    return entry.type_ctor is _parse_dir_set


def _normalized(entry: ConfigEntry, value: str) -> str:
    # a relative directory would otherwise be resolved against whatever folder Speasy later runs from
    if entry.key2.endswith('_dirs'):
        return os.path.abspath(os.path.expanduser(value))
    return value


def _require_list(entry: ConfigEntry) -> ConfigEntry:
    if not is_list_entry(entry):
        raise ValueError(f"{entry.key1.lower()}.{entry.key2} is not a list, use 'speasy config set' instead")
    return entry


def add_values(entry: ConfigEntry, values: Iterable[str]):
    """Adds values to a comma separated list entry, e.g. a directory to archive.extra_inventory_lookup_dirs."""
    current = _require_list(entry).get()
    entry.set(','.join(sorted(current | {_normalized(entry, v) for v in values})))


def remove_values(entry: ConfigEntry, values: Iterable[str]):
    current = _require_list(entry).get()
    entry.set(','.join(sorted(current - {_normalized(entry, v) for v in values})))


def remove_entry(entry: ConfigEntry):
    """Deletes entry from config file and its section if it was the last entry

    Parameters
    ----------
    entry: ConfigEntry
        the entry to delete

    Returns
    -------
    None

    """
    if entry.key1 in _config:
        section = _config[entry.key1]
        if entry.key2 in section:
            section.pop(entry.key2)
        if len(section) == 0:
            _config.remove_section(entry.key1)
        _save_changes()


# ==========================================================================================
#                           ADD HERE CONFIG ENTRIES
# user can easily discover them with speasy.config.<completion>
# ==========================================================================================
core = ConfigSection("CORE",
                     disabled_providers={"default": "",
                                         "description": """A comma separated list of providers you want to disable.
A disabled provider never starts, even when you use it.""",
                                         "type_ctor": _parse_dir_set},
                     http_rewrite_rules={"default": {
                         "https://cdaweb.gsfc.nasa.gov/pub/": "https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/"},
                         "description": """A dictionary of rules to rewrite URLs before sending requests.
The keys are the URL to match and the values are the replacement URL.
Example: {"http://example.com": "http://localhost:8000"}""",
                         "type_ctor": _load_dict_from_repr},
                     http_user_agent={"default": "",
                                        "description": """User agent to use for HTTP requests.
This is useful to identify the application making the request.
If not set, it will use the default user agent of the speasy package."""},
                     urlib_pool_size={"default": 10,
                                      "description": """Sets the maximum number of connections to keep in the pool.
This is useful to avoid creating a new connection for each request.""",
                                      "type_ctor": int},
                     urlib_num_pools={"default": 10,
                                      "description": """Sets the maximum number of pools to keep in the pool.
This is useful to avoid creating a new pool for each request.""",
                                      "type_ctor": int},
                     user_codecs_extra_dirs={"default": "",
                                             "description": """A comma separated list of directories to scan for extra codecs.""",
                                             "type_ctor": _parse_dir_set},
                     disabled_plugins={"default": "",
                                       "description": """A comma separated list of plugin entry-point names to skip, e.g. the
'my_format' of [project.entry-points."speasy.codecs"] my_format = "my_pkg:register".
A bare name disables that plugin in every group; a group-qualified name such as
'speasy.codecs.my_format' disables it in that group only.""",
                                       "type_ctor": _parse_dir_set},
                     )

proxy = ConfigSection("PROXY",
                      enabled={"default": True,
                               "description": """Enables or disables speasy proxy usage.
Speasy proxy is an intermediary server which helps by caching requests among several users.""",
                               "type_ctor": lambda x: {'true': True, 'false': False}.get(x.lower(), False)},
                      url={"default": "https://sciqlop.lpp.polytechnique.fr/cache",
                           "description": """Speasy proxy server URL, you can use https://sciqlop.lpp.polytechnique.fr/cache.
Speasy proxy is an intermediary server which helps by caching requests among several users."""}
                      )

cache = ConfigSection("CACHE",
                      size={"default": 20e9, "description": """Sets the maximum cache capacity.""",
                            "type_ctor": lambda x: int(float(x))},
                      path={"default": str(appdirs.user_cache_dir("speasy", "LPP")),
                            "description": """Sets Speasy cache path."""},
                      migrate_by_moving={"default": True,
                                        "description": """If true, the one-time diskcache -> sciqlop-cache
migration deletes each legacy entry as soon as it's copied, instead of preserving the whole legacy cache
as a rollback backup. Uses much less peak disk space during migration, at the cost of not being able to
fall back to the legacy cache if the new one turns out to have an issue. On by default, since this is
just a cache (data is always re-fetchable) and most users would rather not silently double their disk
usage during migration; set to false to keep the old copy-with-rollback-backup behaviour.""",
                                        "type_ctor": lambda x: {'true': True, 'false': False}.get(x.lower(), False)},
                      )

index = ConfigSection("INDEX",
                      path={
                          "default": f'{appdirs.user_data_dir("speasy", "LPP")}/index'}
                      )
cdaweb = ConfigSection("CDAWEB",
                       inventory_data_path={
                           "default": f'{appdirs.user_data_dir("speasy", "LPP")}/cda_inventory'},
                       preferred_access_method={"default": "BEST",
                                                "description": "Preferred access method to CDAWeb, either REST API (API), dirtect files download (FILE) or BEST to let Speasy choose the fastest and most likely to work method based on the requested product."},
                       )

amda = ConfigSection("AMDA",
                     username={
                         "description": """Your AMDA username, once set, you will be able to get your private products."""},
                     password={
                         "description": """Your AMDA password, once set, you will be able to get your private products."""},
                     user_cache_retention={"default": 900,
                                           "description": "AMDA specific cache retention for requests such as list_catalogs.",
                                           "type_ctor": int
                                           },
                     max_chunk_size_days={
                         "default": 10,
                         "description": "Maximum request duration in days, any request over a longer period will be split into smaller ones.",
                         "type_ctor": int},
                     entry_point={
                         "default": "https://amda.irap.omp.eu"},
                     output_format={
                         "description": "File format requested to AMDA, only CDF_ISTP is supported for now.",
                         "default": "CDF_ISTP"}
                     )

archive = ConfigSection("ARCHIVE",
                        extra_inventory_lookup_dirs={"default": "",
                                                     "description": """A comma separated list of directory path Archive provider will scann for YAML inventory files.""",
                                                     "type_ctor": _parse_dir_set}
                        )

hapi = ConfigSection("HAPI",
                     disabled_servers={"default": "",
                                       "description": """A comma separated list of HAPI servers (keys of speasy.inventories.tree.hapi)
you don't want listed. The servers Speasy serves natively (CDAWeb, AMDA, CSA, SSCWeb) are never listed.""",
                                       "type_ctor": _parse_dir_set},
                     extra_servers={"default": {},
                                    "description": """HAPI servers missing from the official registry, as a {key: url} dictionary.
Example: {"mylab": "https://mylab.example.org/hapi"} gives access to speasy.inventories.tree.hapi.mylab""",
                                    "type_ctor": _load_dict_from_repr}
                     )

inventories = ConfigSection("INVENTORIES",
                            cache_retention_days={
                                "default": 2,
                                "description": "Maximum times in days speasy will keep inventories in cache before fetching newer version.",
                                "type_ctor": int}
                            )
