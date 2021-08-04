import requests
import logging
from enum import Enum

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
        """Constructor
        """
        self.server_url = server_url

    @property
    def get_token(self) -> str:
        """Get authentication token.

        :return: authentication token
        :rtype: str
        """
        # url = "{0}/php/rest/auth.php?".format(self.server_url)
        url = self.request_url(Endpoint.AUTH)
        r = requests.get(url)
        return r.text.strip()

    def request_url(self, endpoint, **kwargs):
        """Get request URL corresponding to an Endpoint of the AMDA REST API.

        :param endpoint: AMDA endpoint
        :type endpoint: Endpoint
        :param kwargs: keyword arguments, if any they are appended to the result
        :type kwargs: dict
        :return: request URL
        :rtype: str
        """
        if len(kwargs):
            return self.request_add_args(self.request_url(endpoint), **kwargs)
        if isinstance(endpoint, Endpoint):
            return "{}/php/rest/{}?".format(self.server_url, endpoint.value)
        return "{}/php/rest/{}?".format(self.server_url, endpoint)

    def request_add_args(self, url, **kwargs: dict):
        """Add set of arguments to input URL.

        :param url: URL
        :type url: str
        :param kwargs: arguments are passed as keyword arguments
        :type kwargs: dict
        :return: URL with appended args
        :rtype: str
        """
        u = url
        for k, v in kwargs.items():
            u += "{}={}&".format(k, v)
        return u

    def send_request(self, url, n_try=3):
        """Send a request to the AMDA REST service. Retry up to :data:`n_try` times upon failure.

        :param url: input URL
        :type url: str
        :param n_try: maximum number of tries
        :type n_try: int
        :return: request result text, stripped of spaces and newlines
        :rtype: str
        """
        url += "token={}".format(self.get_token)
        for _ in [None] * n_try:  # in case of failure
            # add token now ? does it change
            log.debug(f"Send request on AMDA server {url}")
            r = requests.get(url)
            if r is None:
                # try again
                continue
            return r.text.strip()
        return None

    def send_request_double(self, url, n_try=3):
        """Send a request to the AMDA REST service. The request is special in that the result
        is the URL to an XML file containing the actual data we are interested in. That is why
        we call :data:`requests.get()` twice in a row.

        :param url: input URL
        :type url: str
        :param n_try: maximum number of tries
        :type n_try: int
        :return: request result, stripped of spaces and newlines
        :rtype: str
        """
        url += "token={}".format(self.get_token)
        for _ in [None] * n_try:  # in case of failure
            # add token now ? does it change
            log.debug(f"Send request on AMDA server {url}")
            r = requests.get(url)
            r = requests.get(r.text.strip())
            return r.text.strip()
        return None

    def send_request_json(self, url, n_try=3):
        """Send a request to the AMDA REST service. We expect the result to be JSON data.

        :param url: input URL
        :type url: str
        :param n_try: maximum number of tries
        :type n_try: int
        :return: request result
        :rtype: str
        """
        url += "token={}".format(self.get_token)
        for _ in [None] * n_try:  # in case of failure
            # add token now ? does it change
            log.debug(f"Send request on AMDA server {url}")
            r = requests.get(url)
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
        base_url = self.request_url(Endpoint.LISTTT, **kwargs)
        return self.send_request_double(base_url)

    def get_catalog_list(self, **kwargs: dict):
        """Get list of catalogs.

        :param kwargs: keyword arguments, username and password for private catalogs
        :type kwargs: dict
        :return: request result, XML formatted text
        :rtype: str
        """

        base_url = self.request_url(Endpoint.LISTCAT, **kwargs)
        return self.send_request_double(base_url)

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

        base_url = self.request_url(Endpoint.LISTPARAM, userID=username, password=password, **kwargs)
        return self.send_request(base_url)

    def get_timetable(self, **kwargs: dict):
        """Get timetable request.

        :param kwargs: keyword arguments
        :type kwargs: dict
        :return: request result, XML formatted text
        :rtype: str
        """
        base_url = self.request_url(Endpoint.GETTT, **kwargs)
        return self.send_request(base_url)

    def get_catalog(self, **kwargs: dict):
        """Get catalog request.

        :param kwargs: keyword arguments
        :type kwargs: dict
        :return: request result, XML formatted text
        :rtype: str
        """

        base_url = self.request_url(Endpoint.GETCAT, **kwargs)
        return self.send_request(base_url)

    def get_parameter(self, **kwargs: dict):
        """Get parameter request.

        :param kwargs: keyword arguments
        :type kwargs: dict
        :return: request result, JSON
        :rtype: dict
        """
        base_url = self.request_url(Endpoint.GETPARAM, **kwargs)
        return self.send_request_json(base_url)

    def get_obs_data_tree(self):
        """Get observatory data tree.

        :return: observatory data tree
        :rtype: str
        """
        r = requests.get(self.request_url(Endpoint.OBSTREE))
        return r.text.split(">")[1].split("<")[0]
