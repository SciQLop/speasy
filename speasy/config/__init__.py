"""
speasy.config
-------------

Configuration module for SPEASY, it reads or sets config entries first from ENV then from config file.
"""

import configparser
import os
from typing import Any

import appdirs

from ..core import mkdir

SPEASY_CONFIG_DIR = str(appdirs.user_config_dir(appname="speasy", appauthor="LPP"))

SPEASY_CONFIG_FILE = os.path.join(SPEASY_CONFIG_DIR, "config.ini")
mkdir(os.path.dirname(SPEASY_CONFIG_FILE))
_config = configparser.ConfigParser()
_config.read(SPEASY_CONFIG_FILE)

_entries = {}


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
                     disabled_providers={"default": set(),
                                         "description": """A comma separated list of providers you want to disable.
The main benefit of disabling providers is to speedup speasy loading.""",
                                         "type_ctor": lambda x: set(x.split(','))}
                     )

proxy = ConfigSection("PROXY",
                      enabled={"default": True,
                               "description": """Enables or disables speasy proxy usage.
Speasy proxy is an intermediary server which helps by caching requests among several users.""",
                               "type_ctor": lambda x: {'true': True, 'false': False}.get(x.lower(), False)},
                      url={"default": "http://sciqlop.lpp.polytechnique.fr/cache",
                           "description": """Speasy proxy server URL, you can use http://sciqlop.lpp.polytechnique.fr/cache.
Speasy proxy is an intermediary server which helps by caching requests among several users."""}
                      )

cache = ConfigSection("CACHE",
                      size={"default": 20e9, "description": """Sets the maximum cache capacity.""",
                            "type_ctor": lambda x: int(float(x))},
                      path={"default": str(appdirs.user_cache_dir("speasy", "LPP")),
                            "description": """Sets Speasy cache path."""}
                      )

index = ConfigSection("INDEX",
                      path={
                          "default": f'{appdirs.user_data_dir("speasy", "LPP")}/index'}
                      )
cdaweb = ConfigSection("CDAWEB",
                       inventory_data_path={
                           "default": f'{appdirs.user_data_dir("speasy", "LPP")}/cda_inventory'}
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
                         "description": "File format requested to AMDA, either ASCII or CDF_ISTP",
                         "default": "CDF_ISTP"}
                     )

archive = ConfigSection("ARCHIVE",
                        extra_inventory_lookup_dirs={"default": set(),
                                                     "description": """A comma separated list of directory path Archive provider will scann for YAML inventory files.""",
                                                     "type_ctor": lambda x: set(x.split(','))}
                        )

inventories = ConfigSection("INVENTORIES",
                            cache_retention_days={
                                "default": 2,
                                "description": "Maximum times in days speasy will keep inventories in cache before fetching newer version.",
                                "type_ctor": int}
                            )
