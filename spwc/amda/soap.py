from zeep import Client


class AmdaSoap:
    def __init__(self, server_url="http://amda.irap.omp.eu", wsdl='AMDA/public/wsdl/Methods_AMDA.wsdl', strict=True):
        self.soap_client = Client(server_url + '/' + wsdl)
        self.server_url = server_url

    def get_parameter(self, **kwargs):
        resp = self.soap_client.service.getParameter(**kwargs).__json__()
        if resp["success"]:
            return resp["dataFileURLs"][0]
        else:
            return None

    def get_obs_data_tree(self):
        resp = self.soap_client.service.getObsDataTree().__json__()
        if resp["success"]:
            return resp["WorkSpace"]["LocalDataBaseParameters"]
        else:
            return None
