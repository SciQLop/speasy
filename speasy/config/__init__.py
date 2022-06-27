"""
speasy.config
-------------

Configuration module for SPEASY, it reads or sets config entries first from ENV then from config file.
"""

import configparser
import os
import appdirs
from ..core import mkdir

_CONFIG_FNAME = str(appdirs.user_config_dir(appname="speasy", appauthor="LPP")) + "/config.ini"
mkdir(os.path.dirname(_CONFIG_FNAME))
_config = configparser.ConfigParser()
_config.read(_CONFIG_FNAME)

_entries = {}


def _register_entry(entry):
    if entry.key1 not in _entries:
        _entries[entry.key1] = {}
    _entries[entry.key1][entry.key2] = entry


def show():
    for section_name, section in _entries.items():
        print(f"""
============================================
\t\t{section_name}
============================================""")
        for _, entry in section.items():
            print(f"\n  {entry}")
            print('-------------------------------------------')


def _save_changes():
    with open(_CONFIG_FNAME, 'w') as f:
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
        Default value given by ctor
    env_var_name: str
        Environment variable name to use to set this entry

    Methods
    -------
    get:
        Get entry current value
    set:
        Set entry value (could be env or file)
    """

    def __init__(self, key1: str, key2: str, default: str = "", description: str = ""):
        self.key1 = key1
        self.key2 = key2
        self.default = default
        self.description = description
        _register_entry(self)
        self.env_var_name = f"SPEASY_{self.key1}_{self.key2}".upper().replace('-', '_')

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
            return os.environ[self.env_var_name]
        if self.key1 in _config and self.key2 in _config[self.key1]:
            return _config[self.key1][self.key2]
        return self.default

    def set(self, value: str):
        if self.env_var_name in os.environ:
            os.environ[self.env_var_name] = value
        if self.key1 not in _config:
            _config.add_section(self.key1)
        _config[self.key1][self.key2] = value
        _save_changes()


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

proxy_enabled = ConfigEntry("PROXY", "enabled", "False",
                            description="""Enables or disables speasy proxy usage.
Speasy proxy is an intermediary server which helps by caching requests among several users.""")
proxy_url = ConfigEntry("PROXY", "url", "",
                        description="""Speasy proxy server URL, you can use http://sciqlop.lpp.polytechnique.fr/cache.
Speasy proxy is an intermediary server which helps by caching requests among several users.""")

cache_size = ConfigEntry("CACHE", "size", "20e9", description="""Sets the maximum cache capacity.""")
cache_path = ConfigEntry("CACHE", "path", str(appdirs.user_cache_dir("speasy", "LPP")),
                         description="""Sets Speasy cache path.""")

amda_username = ConfigEntry("AMDA", "username",
                            description="""Your AMDA username, once set, you will be able to get your private products.""")
amda_password = ConfigEntry("AMDA", "password",
                            description="""Your AMDA password, once set, you will be able to get your private products.""")
amda_user_cache_retention = ConfigEntry("AMDA", "user_cache_retention", "900",
                                        description="AMDA specific cache retention for requests such as list_catalogs.")  # 60 * 15 seconds
amda_max_chunk_size_days = ConfigEntry("AMDA", "max_chunk_size_days", "10",
                                       description="Maximum request duration in days, any request over a longer period will be split in smaller ones.")
