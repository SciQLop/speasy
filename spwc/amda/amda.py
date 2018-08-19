from .rest import AmdaRest
from .soap import AmdaSoap
import xmltodict
from datetime import datetime
import pandas as pds
import requests
from ..common import listify


class AMDA:

    def __init__(self, wsdl: str = 'AMDA/public/wsdl/Methods_AMDA.wsdl', server_url: str = "http://amda.irap.omp.eu"):
        self.METHODS = {
            "REST": AmdaRest(server_url=server_url),
            "SOAP": AmdaSoap(server_url=server_url, wsdl=wsdl)
        }

    def get_token(self, method: str = "SOAP", **kwargs: dict) -> str:
        return self.METHODS[method.upper()].get_token

    def get_parameter(self, start_time: str or datetime, stop_time: str or datetime, parameter_id: str,
                      method: str = "SOAP", **kwargs) -> pds.DataFrame or None:
        if type(start_time) is datetime:
            start_time = start_time.isoformat()
        if type(stop_time) is datetime:
            stop_time = stop_time.isoformat()
        url = self.METHODS[method.upper()].get_parameter(
            startTime=start_time, stopTime=stop_time, parameterID=parameter_id, **kwargs)
        if url is not None:
            return pds.read_csv(url, delim_whitespace=True, comment='#', parse_dates=True, infer_datetime_format=True,
                                index_col=0, header=None)
        return None

    def get_obs_data_tree(self, method="SOAP"):
        data_tree = xmltodict.parse(requests.get(self.METHODS[method.upper()].get_obs_data_tree().text))
        for mission in data_tree["dataRoot"]["dataCenter"]["mission"]:
            for instrument in listify(mission["instrument"]):
                for dataset in listify(instrument['dataset']):
                    for parameter in listify(dataset['parameter']):
                        if 'component' in parameter:
                            parameter['component'] = {
                                comp["@name"]: comp for comp in listify(parameter['component'])
                            }
                    dataset['parameter'] = {
                        param["@name"]: param for param in listify(dataset['parameter'])}
                instrument['dataset'] = {
                    dataset["@name"]: dataset for dataset in listify(instrument['dataset'])}
            mission["instrument"] = {
                instrument["@name"]: instrument for instrument in listify(mission["instrument"])}
        data_tree["dataRoot"]["dataCenter"]["mission"] = {
            mission["@name"]: mission for mission in data_tree["dataRoot"]["dataCenter"]["mission"]}
        return data_tree
