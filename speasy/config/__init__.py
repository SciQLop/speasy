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

    def __init__(self, key1: str, key2: str, default: str = ""):
        self.key1 = key1
        self.key2 = key2
        self.default = default
        self.env_var_name = f"SPEASY_{self.key1}_{self.key2}".upper().replace('-', '_')

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

proxy_enabled = ConfigEntry("PROXY", "enabled", "False")
proxy_url = ConfigEntry("PROXY", "url", "")

cache_size = ConfigEntry("CACHE", "size", "20e9")
cache_path = ConfigEntry("CACHE", "path", str(appdirs.user_cache_dir("speasy", "LPP")))

amda_username = ConfigEntry("AMDA", "username")
amda_password = ConfigEntry("AMDA", "password")
amda_user_cache_retention = ConfigEntry("AMDA", "user_cache_retention", "900")  # 60 * 15 seconds
