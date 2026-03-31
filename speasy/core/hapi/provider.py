from typing import List, Mapping, Optional

from speasy.products.variable import SpeasyVariable

from .client import HapiClient


class HapiProvider:
    def __init__(self, server_url: str):
        self.hapi_client = HapiClient(server_url)

    def hapi(self) -> str:
        return self.hapi_client.get_hapi()

    def capabilities(self) -> dict:
        return self.hapi_client.get_capabilities()

    def catalog(self) -> dict:
        return self.hapi_client.get_catalog()

    def about(self) -> dict:
        return self.hapi_client.get_about()

    def info(self, dataset: str, parameters: Optional[List] = None) -> dict:
        return self.hapi_client.get_info(dataset, parameters)

    def data(self, dataset: str, start: str, stop: str,
             parameters: List[str]) -> Mapping[str, SpeasyVariable]:
        return self.hapi_client.get_data(dataset, start, stop, parameters)
