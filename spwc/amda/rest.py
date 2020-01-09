import requests
import logging

log = logging.getLogger(__name__)


class AmdaRest:
    def __init__(self, server_url="http://amda.irap.omp.eu"):
        self.server_url = server_url

    def get_parameter(self, **kwargs: dict):
        base_url = "{0}/php/rest/getParameter.php?".format(self.server_url)
        key: str
        for key, val in kwargs.items():
            base_url += key + "=" + str(val) + "&"
        for _ in [None] * 3:  # sometime fails with no reason...
            url = base_url + "token=" + self.get_token
            log.debug(f"Send request on AMDA server {url}")
            r = requests.get(url)
            js = r.json()
            if 'success' in js and js['success'] is True and 'dataFileURLs' in js:
                log.debug(f"success: {js['dataFileURLs']}")
                return js['dataFileURLs']
            else:
                log.debug(f"Failed: {r.text}")
        return None

    @property
    def get_token(self) -> str:
        url = "{0}/php/rest/auth.php?".format(self.server_url)
        r = requests.get(url)
        return r.text

    def get_obs_data_tree(self):
        url = self.server_url + "/php/rest/getObsDataTree.php"
        r = requests.get(url)
        return r.text.split(">")[1].split("<")[0]
