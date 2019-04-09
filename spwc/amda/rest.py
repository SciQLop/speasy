import requests


class AmdaRest:
    def __init__(self, server_url="http://amda.irap.omp.eu"):
        self.server_url = server_url

    def get_parameter(self, **kwargs: dict):
        url = "{0}/php/rest/getParameter.php?".format(self.server_url)
        key: str
        for key, val in kwargs.items():
            url += key + "=" + str(val) + "&"
        r = requests.get(url+"&token="+self.get_token)
        print(url)
        if 'success' in r.json():
            return r.json()['dataFileURLs']
        else:
            print(r.text)
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
