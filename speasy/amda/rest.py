import logging
from enum import Enum

from ..common import http, all_kwargs

log = logging.getLogger(__name__)


class Endpoint(Enum):
    """AMDA REST API endpoints.
    """
    AUTH = "auth.php"
    OBSTREE = "getObsDataTree.php"

    LISTTT = "getTimeTablesList.php"
    LISTCAT = "getCatalogsList.php"
    LISTPARAM = "getParameterList.php"

    GETTT = "getTimeTable.php"
    GETCAT = "getCatalog.php"
    GETPARAM = "getParameter.php"


class AmdaRest:
    """AMDA REST client.

    :param server_url: AMDA REST service URL
    :type server_url: str
    """

    def __init__(self, server_url="http://amda.irap.omp.eu"):
        self.server_url = server_url

    @property
    def token(self) -> str:
        """Returns authentication token.

        :return: authentication token
        :rtype: str
        """
        # url = "{0}/php/rest/auth.php?".format(self.server_url)
        r = http.get(self.request_url(Endpoint.AUTH))
        if r.status_code == 200 and r.ok:
            return r.text.strip()
        else:
            raise RuntimeError("Failed to get auth token")

    def request_url(self, endpoint):
        """Generates full URL for the given endpoint.

        :param endpoint: request endpoint
        :type endpoint: Endpoint
        :return: request URL
        :rtype: str
        """
        if isinstance(endpoint, Endpoint):
            return f"{self.server_url}/php/rest/{endpoint.value}"
        else:
            raise TypeError(f"You must provide an {Endpoint} instead of {type(endpoint)}")

    def send_request(self, endpoint: Endpoint, params: dict = None, n_try=3):
        """Send a request on the AMDA REST service to the given endpoint with given parameters. Retry up to :data:`n_try` times upon failure.

        :param endpoint: request endpoint
        :type endpoint: Endpoint
        :param params: request parameters
        :type params: dict
        :param n_try: maximum number of tries
        :type n_try: int
        :return: request result text, stripped of spaces and newlines
        :rtype: str
        """
        url = self.request_url(endpoint)
        params = params or {}
        params['token'] = self.token
        for _ in [None] * n_try:  # in case of failure
            # add token now ? does it change
            log.debug(f"Send request on AMDA server {url}")
            r = http.get(url, params=params)
            if r is None:
                # try again
                continue
            return r.text.strip()
        return None

    def send_indirect_request(self, endpoint: Endpoint, params: dict = None, n_try=3):
        """Send a request on the AMDA REST service to the given endpoint with given parameters. The request is special in that the result
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
        url = self.request_url(endpoint)
        params = params or {}
        params['token'] = self.token
        for _ in [None] * n_try:  # in case of failure
            # add token now ? does it change
            log.debug(f"Send request on AMDA server {url}")
            r = http.get(url, params=params)
            r = http.get(r.text.strip())
            return r.text.strip()
        return None

    def send_request_json(self, endpoint: Endpoint, params=None, n_try=3):
        """Send a request on the AMDA REST service to the given endpoint with given parameters. We expect the result to be JSON data.

        :param endpoint: request endpoint
        :type endpoint: Endpoint
        :param params: request parameters
        :type params: dict
        :param n_try: maximum number of tries
        :type n_try: int
        :return: request result
        :rtype: str
        """
        url = self.request_url(endpoint)
        params = params or {}
        params['token'] = self.token
        for _ in [None] * n_try:  # in case of failure
            # add token now ? does it change
            log.debug(f"Send request on AMDA server {url}")
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

    def get_timetable_list(self, **kwargs: dict):
        """Get list of timetables.

        :param kwargs: keyword arguments, username and password for private timetables
        :type kwargs: dict
        :return: request result, XML formatted text
        :rtype: str
        """
        return self.send_indirect_request(Endpoint.LISTTT, params=kwargs)

    def get_catalog_list(self, **kwargs: dict):
        """Get list of catalogs.

        :param kwargs: keyword arguments, username and password for private catalogs
        :type kwargs: dict
        :return: request result, XML formatted text
        :rtype: str
        """
        return self.send_indirect_request(Endpoint.LISTCAT, params=kwargs)

    def list_user_timetables(self, username, password, **kwargs: dict):
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
        return self.get_timetable_list(userID=username, password=password, **kwargs)

    def list_user_catalogs(self, username, password, **kwargs: dict):
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
        return self.get_catalog_list(userID=username, password=password, **kwargs)

    def get_user_parameters(self, username, password, **kwargs: dict):
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
        return self.send_request(Endpoint.LISTPARAM, params=all_kwargs(**kwargs, userID=username, password=password))

    def get_timetable(self, **kwargs: dict):
        """Get timetable request.

        :param kwargs: keyword arguments
        :type kwargs: dict
        :return: request result, XML formatted text
        :rtype: str
        """
        return self.send_request(Endpoint.GETTT, params=kwargs)

    def get_catalog(self, **kwargs: dict):
        """Get catalog request.

        :param kwargs: keyword arguments
        :type kwargs: dict
        :return: request result, XML formatted text
        :rtype: str
        """

        return self.send_request(Endpoint.GETCAT, params=kwargs)

    def get_parameter(self, **kwargs: dict):
        """Get parameter request.

        :param kwargs: keyword arguments
        :type kwargs: dict
        :return: request result, JSON
        :rtype: dict
        """
        return self.send_request_json(Endpoint.GETPARAM, params=kwargs)

    def get_obs_data_tree(self):
        """Get observatory data tree.

        :return: observatory data tree
        :rtype: str
        """
        r = http.get(self.request_url(Endpoint.OBSTREE))
        return r.text.split(">")[1].split("<")[0]
