import logging
from enum import Enum

from speasy.core import http, pack_kwargs
from speasy.core.cache import CacheCall
from speasy.config import amda_user_cache_retention

import xml.etree.ElementTree as Et

log = logging.getLogger(__name__)


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


def auth_args(username: str, password: str) -> dict:
    return {'userID': username, 'password': password}


def request_url(endpoint, server_url):
    """Generates full URL for the given endpoint.

    :param endpoint: request endpoint
    :type endpoint: Endpoint
    :return: request URL
    :rtype: str
    """
    if isinstance(endpoint, Endpoint):
        return f"{server_url}/php/rest/{endpoint.value}"
    else:
        raise TypeError(f"You must provide an {Endpoint} instead of {type(endpoint)}")


def token(server_url="http://amda.irap.omp.eu") -> str:
    """Returns authentication token.

    :return: authentication token
    :rtype: str
    """
    # url = "{0}/php/rest/auth.php?".format(self.server_url)
    r = http.get(request_url(Endpoint.AUTH, server_url=server_url))
    if r.status_code == 200:
        return r.text.strip()
    else:
        raise RuntimeError("Failed to get auth token")


def send_request(endpoint: Endpoint, params: dict = None, n_try=3, server_url="http://amda.irap.omp.eu"):
    """Send a request on the AMDA_Webservice REST service to the given endpoint with given parameters. Retry up to :data:`n_try` times upon failure.

    :param endpoint: request endpoint
    :type endpoint: Endpoint
    :param params: request parameters
    :type params: dict
    :param n_try: maximum number of tries
    :type n_try: int
    :return: request result text, stripped of spaces and newlines
    :rtype: str
    """
    url = request_url(endpoint, server_url=server_url)
    params = params or {}
    params['token'] = token(server_url=server_url)
    for _ in [None] * n_try:  # in case of failure
        # add token now ? does it change
        log.debug(f"Send request on AMDA_Webservice server {url}")
        r = http.get(url, params=params)
        if r is None:
            # try again
            continue
        return r.text.strip()
    return None


def send_indirect_request(endpoint: Endpoint, params: dict = None, n_try=3,
                          server_url="http://amda.irap.omp.eu"):
    """Send a request on the AMDA_Webservice REST service to the given endpoint with given parameters. The request is special in that the result
    is the URL to an XML file containing the actual data we are interested in. That is why
    we call :data:`requests.get()` twice in a row.

    :param endpoint: request endpoint
    :type endpoint: Endpoint
    :param params: request parameters
    :type params: dict
    :param n_try: maximum number of tries
    :type n_try: int
    :return: request result, stripped of spaces and newlines
    :rtype: str
    """
    next_url = send_request(endpoint=endpoint, params=params, n_try=n_try, server_url=server_url)
    if '<' in next_url and '>' in next_url:
        next_url = next_url.split(">")[1].split("<")[0]
    r = http.get(next_url)
    if r.status_code == 200:
        return r.text.strip()
    return None


def send_request_json(endpoint: Endpoint, params=None, n_try=3, server_url="http://amda.irap.omp.eu"):
    """Send a request on the AMDA_Webservice REST service to the given endpoint with given parameters. We expect the result to be JSON data.

    :param endpoint: request endpoint
    :type endpoint: Endpoint
    :param params: request parameters
    :type params: dict
    :param n_try: maximum number of tries
    :type n_try: int
    :return: request result
    :rtype: str
    """
    url = request_url(endpoint, server_url=server_url)
    params = params or {}
    params['token'] = token(server_url=server_url)
    for _ in [None] * n_try:  # in case of failure
        # add token now ? does it change
        log.debug(f"Send request on AMDA_Webservice server {url}")
        r = http.get(url, params=params)
        js = r.json()
        if 'success' in js and \
            js['success'] is True and \
            'dataFileURLs' in js:
            log.debug(f"success: {js['dataFileURLs']}")
            return js['dataFileURLs']
        else:
            log.debug(f"Failed: {r.text}")
    return None


@CacheCall(cache_retention=float(amda_user_cache_retention.get()), is_pure=True)
def get_timetables_xml_tree(server_url="http://amda.irap.omp.eu", **kwargs: str):
    """Get list of timetables.

    :param kwargs: keyword arguments, username and password for private timetables
    :type kwargs: dict
    :return: request result, XML formatted text
    :rtype: str
    """
    return send_indirect_request(Endpoint.LISTTT, params=kwargs, server_url=server_url)


@CacheCall(cache_retention=float(amda_user_cache_retention.get()), is_pure=True)
def get_catalogs_xml_tree(server_url="http://amda.irap.omp.eu", **kwargs: str):
    """Get list of catalogs.

    :param kwargs: keyword arguments, username and password for private catalogs
    :type kwargs: dict
    :return: request result, XML formatted text
    :rtype: str
    """
    return send_indirect_request(Endpoint.LISTCAT, params=kwargs, server_url=server_url)


@CacheCall(cache_retention=float(amda_user_cache_retention.get()), is_pure=True)
def get_user_timetables_xml_tree(username, password, server_url="http://amda.irap.omp.eu", **kwargs: str):
    """Get private timetables.

    :param username: username
    :type username: str
    :param password: password
    :type password: str
    :param kwargs: keyword arguments for the request
    :type kwargs: dict
    :return: request result, XML formatted text
    :rtype: str
    """
    return get_timetables_xml_tree(**auth_args(username, password), **kwargs, server_url=server_url)


@CacheCall(cache_retention=float(amda_user_cache_retention.get()), is_pure=True)
def get_user_catalogs_xml_tree(username: str, password: str, server_url="http://amda.irap.omp.eu",
                               **kwargs: str):
    """Get private catalogs.

    :param username: username
    :type username: str
    :param password: password
    :type password: str
    :param kwargs: keyword arguments for the request
    :type kwargs: dict
    :return: request result, XML formatted text
    :rtype: str
    """
    return get_catalogs_xml_tree(**auth_args(username, password), **kwargs, server_url=server_url)


@CacheCall(cache_retention=float(amda_user_cache_retention.get()), is_pure=True)
def get_user_parameters_xml_tree(username, password, server_url="http://amda.irap.omp.eu", **kwargs: str):
    """Get private parameters.

    :param username: username
    :type username: str
    :param password: password
    :type password: str
    :param kwargs: keyword arguments for the request
    :type kwargs: dict
    :return: request result, XML formatted text
    :rtype: str
    """
    xml_resp = send_request(Endpoint.LISTPARAM, params=pack_kwargs(**kwargs, **auth_args(username, password)),
                            server_url=server_url).strip()
    node = Et.fromstring(f'<root>{xml_resp}</root>').find("UserDefinedParameters")
    if node is not None:
        return http.get(node.text).text
    return None


@CacheCall(cache_retention=float(amda_user_cache_retention.get()), is_pure=True)
def get_timetable(server_url="http://amda.irap.omp.eu", **kwargs: str):
    """Get timetable request.

    :param kwargs: keyword arguments
    :type kwargs: dict
    :return: request result, XML formatted text
    :rtype: str
    """
    return send_request(Endpoint.GETTT, params=kwargs, server_url=server_url)


@CacheCall(cache_retention=float(amda_user_cache_retention.get()), is_pure=True)
def get_catalog(server_url="http://amda.irap.omp.eu", **kwargs: str):
    """Get catalog request.

    :param kwargs: keyword arguments
    :type kwargs: dict
    :return: request result, XML formatted text
    :rtype: str
    """

    return send_request(Endpoint.GETCAT, params=kwargs, server_url=server_url)


def get_parameter(server_url="http://amda.irap.omp.eu", **kwargs: str):
    """Get parameter request.

    :param kwargs: keyword arguments
    :type kwargs: dict
    :return: request result, JSON
    :rtype: dict
    """
    return send_request_json(Endpoint.GETPARAM, params=kwargs, server_url=server_url)


@CacheCall(cache_retention=24 * 60 * 60, is_pure=True)
def get_obs_data_tree(server_url="http://amda.irap.omp.eu"):
    """Get observatory data tree.

    :return: observatory data tree
    :rtype: str
    """
    return send_indirect_request(Endpoint.OBSTREE, server_url=server_url)
