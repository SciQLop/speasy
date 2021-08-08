"""
speasy.config
-------------

Configuration module.
"""

import configparser, os
import appdirs
from ..common import mkdir
from .exceptions import *

_CONFIG_FNAME = str(appdirs.user_config_dir(appname="speasy", appauthor="LPP")) + "/config.ini"
mkdir(os.path.dirname(_CONFIG_FNAME))
_config = configparser.ConfigParser()
_config.read(_CONFIG_FNAME)



class ConfigEntry:
    """Configuration entry class. Used to set and get configuration values.

    :param key1: key 1
    :type key1: str
    :param key2: key 2
    :type key2: str
    :param default: default value
    :type default: str
    """
    def __init__(self, key1, key2, default=""):
        self.key1 = key1
        self.key2 = key2
        self.default = default

    def get(self):
        """Get configuration entry value. If a default is not provided then raise :class:`~speasy.config.exceptions.UndefinedConfigEntry`.

        :return: configuration value
        :rtype: str
        """
        if self.key1 in _config and self.key2 in _config[self.key1]:
            return _config[self.key1][self.key2]
        return self.default


    def set(self, value):
        if self.key1 not in _config:
            _config.add_section(self.key1)
        _config[self.key1][self.key2] = value
        with open(_CONFIG_FNAME, 'w') as f:
            _config.write(f)


proxy_enabled = ConfigEntry("PROXY", "enabled", "False")
proxy_url = ConfigEntry("PROXY", "url", "")

cache_size = ConfigEntry("CACHE", "size", "20e9")
cache_path = ConfigEntry("CACHE", "path", str(appdirs.user_cache_dir("speasy", "LPP")))

amda_username = ConfigEntry("AMDA", "username")
amda_password = ConfigEntry("AMDA", "password")
