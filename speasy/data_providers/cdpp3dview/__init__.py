# -*- coding: utf-8 -*-

"""Cdpp 3dView package for Space Physics WebServices Client."""

__author__ = """Richard Hitier"""
__email__ = 'hitier.richard@gmail.com'
__version__ = '0.1.0'

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

from speasy.core.dataprovider import DataProvider

log = logging.getLogger(__name__)


class Cdpp3dViewWebservice(DataProvider):
    BASE_URL = "https://3dview.irap.omp.eu/webresources"

    def __init__(self):
        self.__url = f"{self.BASE_URL}/WS/sscr/2"
        DataProvider.__init__(self, provider_name='cdpp3dview', provider_alt_names=['cdpp3d'])