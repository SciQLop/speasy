import logging
import time
from enum import Enum

from speasy.core import http, pack_kwargs
from speasy.core.cache import CacheCall
from speasy.config import amda as amda_cfg

import xml.etree.ElementTree as Et

from typing import Dict

log = logging.getLogger(__name__)

AMDA_BATCH_MODE_TIME = 240  # seconds


class Endpoint(Enum):
    """AMDA_Webservice REST API endpoints.
    """
    AUTH = "auth.php"
    OBSTREE = "getObsDataTree.php"

    LISTTT = "getTimeTablesList.php"
    LISTCAT = "getCatalogsList.php"
    LISTPARAM = "getParameterList.php"

    GETTT = "getTimeTable.php"
    GETCAT = "getCatalog.php"
    GETPARAM = "getParameter.php"

    GETSTATUS = "getStatus.php"


def auth_args(username: str, password: str) -> dict:
    return {'userID': username, 'password': password}


def request_url(endpoint: Endpoint, server_url: str) -> str:
    """Generates full URL for the given endpoint.

    Parameters
    ----------
    endpoint: Endpoint
        target API endpoint
    server_url: str
        server base url

    Returns
    -------
    str
        full URL to perform a request on the given API endpoint
    """
    if isinstance(endpoint, Endpoint):
        return f"{server_url}/php/rest/{endpoint.value}"
    else:
        raise TypeError(f"You must provide an {Endpoint} instead of {type(endpoint)}")


def token(server_url: str = amda_cfg.entry_point()) -> str:
    """Returns authentication token.

    Parameters
    ----------
    server_url:str
        server base URL on which the API token will be generated

    Returns
    -------
    str
        the generated token
    """
    # url = "{0}/php/rest/auth.php?".format(self.server_url)
    r = http.get(request_url(Endpoint.AUTH, server_url=server_url))
    if r.status_code == 200:
        return r.text.strip()
    else:
        raise RuntimeError("Failed to get auth token")


def send_request(endpoint: Endpoint, params: dict = None, timeout: int = http.DEFAULT_TIMEOUT,
                 server_url: str = amda_cfg.entry_point()) -> str or None:
    """Send a request on the AMDA_Webservice REST service to the given endpoint with given parameters.

    Parameters
    ----------
    endpoint: Endpoint
        target API endpoint on which the request will be performed
    params: dict
        request parameters
    timeout: int
        request timeout
    server_url: str
        the base server URL

    Returns
    -------
    str or None
        request result text, stripped of spaces and newlines

    """
    url = request_url(endpoint, server_url=server_url)
    params = params or {}
    params['token'] = token(server_url=server_url)
    r = http.get(url, params=params, timeout=timeout)
    if r.status_code == 200:
        return r.text.strip()
    return None


def send_indirect_request(endpoint: Endpoint, params: dict = None,
                          timeout: int = http.DEFAULT_TIMEOUT,
                          server_url: str = amda_cfg.entry_point()) -> str or None:
    """Send a request on the AMDA_Webservice REST service to the given endpoint with given parameters.
    The request is special in that the result is the URL to an XML file containing
    the actual data we are interested in. That is why we call :data:`requests.get()` twice in a row.

    Parameters
    ----------
    endpoint: Endpoint
        target API endpoint on which the request will be performed
    params: dict
        request parameters
    timeout: int
        request timeout
    server_url: str
        the base server URL

    Returns
    -------
    str or None
        request result text, stripped of spaces and newlines

    """
    next_url = send_request(endpoint=endpoint, params=params, timeout=timeout, server_url=server_url)
    if '<' in next_url and '>' in next_url:
        next_url = next_url.split(">")[1].split("<")[0]
    r = http.get(next_url, timeout=timeout)
    if r.status_code == 200:
        return r.text.strip()
    return None


def send_request_json(endpoint: Endpoint, params: Dict = None, timeout: int = http.DEFAULT_TIMEOUT,
                      server_url: str = amda_cfg.entry_point(),
                      extra_http_headers: Dict or None = None) -> str or None:
    """Send a request on the AMDA_Webservice REST service to the given endpoint with given parameters.
    We expect the result to be JSON data.

    Parameters
    ----------
    endpoint: Endpoint
        target API endpoint on which the request will be performed
    params: dict
        request parameters
    timeout: int
        request timeout
    server_url: str
        the base server URL

    Returns
    -------
    str or None
        request result parsed as json object
    """

    url = request_url(endpoint, server_url=server_url)
    params = params or {}
    http_headers = extra_http_headers or {}
    params['token'] = token(server_url=server_url)
    r = http.get(url, params=params, headers=http_headers, timeout=timeout)
    js = r.json()
    if 'success' in js and \
       js['success'] is True and \
       'dataFileURLs' in js:
        log.debug(f"success: {js['dataFileURLs']}")
        return js['dataFileURLs']
    elif "success" in js and \
         js["success"] is True and \
         "status" in js and \
         js["status"] == "in progress":
        log.warning("This request duration is too long, consider reducing time range")
        while True:
            default_sleep_time = 10.
            time.sleep(default_sleep_time)
            url = request_url(Endpoint.GETSTATUS, server_url=server_url)

            status = http.get(url, params=js, headers=http_headers).json()
            if status is not None and status["status"] == "done":
                return status["dataFileURLs"]
    else:
        log.debug(f"Failed: {r.text}")
    return None


@CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
def get_timetables_xml_tree(server_url: str = amda_cfg.entry_point(), **kwargs: Dict) -> str or None:
    """Get list of timetables.

    Parameters
    ----------
    server_url: str
        the base server URL
    kwargs: dict
        extra request arguments such as username and password for private timetables

    Returns
    -------
    str or None
        request result, XML formatted text

    """
    return send_indirect_request(Endpoint.LISTTT, params=kwargs, server_url=server_url)


@CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
def get_catalogs_xml_tree(server_url: str = amda_cfg.entry_point(), **kwargs: Dict) -> str or None:
    """Get list of catalogs.

    Parameters
    ----------
    server_url: str
        the base server URL
    kwargs: dict
        extra request arguments such as username and password for private catalogs

    Returns
    -------
    str or None
        request result, XML formatted text
    """
    return send_indirect_request(Endpoint.LISTCAT, params=kwargs, server_url=server_url)


@CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
def get_user_timetables_xml_tree(username: str, password: str, server_url: str = amda_cfg.entry_point(),
                                 **kwargs: Dict) -> str or None:
    """Get private list of timetables.

    Parameters
    ----------
    username: str
        AMDA username
    password:
        AMDA password
    server_url: str
        the base server URL
    kwargs: dict
        extra request arguments

    Returns
    -------
    str or None
        request result, XML formatted text
    """
    return get_timetables_xml_tree(**auth_args(username, password), **kwargs, server_url=server_url)


@CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
def get_user_catalogs_xml_tree(username: str, password: str, server_url: str = amda_cfg.entry_point(),
                               **kwargs: Dict) -> str or None:
    """Get private list of catalogs.

    Parameters
    ----------
    username: str
        AMDA username
    password:
        AMDA password
    server_url: str
        the base server URL
    kwargs: dict
        extra request arguments

    Returns
    -------
    str or None
        request result, XML formatted text
    """
    return get_catalogs_xml_tree(**auth_args(username, password), **kwargs, server_url=server_url)


@CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
def get_user_parameters_xml_tree(username: str, password: str, server_url: str = amda_cfg.entry_point(),
                                 **kwargs: Dict) -> str or None:
    """Get private list of parameters.

    Parameters
    ----------
    username: str
        AMDA username
    password:
        AMDA password
    server_url: str
        the base server URL
    kwargs: dict
        extra request arguments

    Returns
    -------
    str or None
        request result, XML formatted text
    """
    xml_resp = send_request(Endpoint.LISTPARAM, params=pack_kwargs(**kwargs, **auth_args(username, password)),
                            server_url=server_url).strip()
    node = Et.fromstring(f'<root>{xml_resp}</root>').find("UserDefinedParameters")
    if node is not None:
        return http.get(node.text).text
    return None


@CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
def get_timetable(server_url: str = amda_cfg.entry_point(), **kwargs: Dict) -> str or None:
    """Get timetable request.

    Parameters
    ----------
    server_url: str
        the base server URL
    kwargs: dict
        extra request arguments such as username and password for private timetables

    Returns
    -------
    str or None
        request result, XML formatted text
    """
    return send_request(Endpoint.GETTT, params=kwargs, server_url=server_url)


@CacheCall(cache_retention=amda_cfg.user_cache_retention(), is_pure=True)
def get_catalog(server_url: str = amda_cfg.entry_point(), **kwargs: Dict) -> str or None:
    """Get catalog request.

    Parameters
    ----------
    server_url: str
        the base server URL
    kwargs: dict
        extra request arguments such as username and password for private catalogs

    Returns
    -------
    str or None
        request result, XML formatted text
    """

    return send_request(Endpoint.GETCAT, params=kwargs, server_url=server_url)


def get_parameter(server_url: str = amda_cfg.entry_point(), extra_http_headers: Dict or None = None,
                  **kwargs: Dict) -> str or None:
    """Get parameter request.

    Parameters
    ----------
    extra_http_headers : Dict or None
        reserved for internal use
    server_url: str
        the base server URL
    kwargs: dict
        extra request arguments such as username and password for private parameters

    Returns
    -------
    str or None
        request result, XML formatted text
    """
    return send_request_json(Endpoint.GETPARAM, params=kwargs, server_url=server_url, timeout=AMDA_BATCH_MODE_TIME+10,
                             extra_http_headers=extra_http_headers)


@CacheCall(cache_retention=24 * 60 * 60, is_pure=True)
def get_obs_data_tree(server_url: str = amda_cfg.entry_point()) -> str or None:
    """Get observatory data tree.

    Parameters
    ----------
    server_url: str
        the base server URL

    Returns
    -------
    str or None
        request result, XML formatted text
    """
    return send_indirect_request(Endpoint.OBSTREE, server_url=server_url)
