from typing import List, Optional

from speasy.core.hapi.exceptions import HapiRequestError, HapiServerError
from speasy.products.variable import SpeasyVariable

from .client import HapiClient

def _exception_to_error_message(e):
    error_type = "request" if isinstance(e, HapiRequestError) else "server"
    error_message =  {
        "error": error_type,
        "code": getattr(e, "code", None),
        "message": str(e),
    }
    return error_message


class HapiProvider:
    def __init__(self, server_url: str):
        self.hapi_client = HapiClient(server_url)

    def hapi(self) -> dict:
        return self.hapi_client.get_hapi()

    def capabilities(self) -> dict:
        return self.hapi_client.get_capabilities()

    def catalog(self) -> dict:
        return self.hapi_client.get_catalog()

    def about(self) -> dict:
        return self.hapi_client.get_about()

    def info(self, dataset: str, parameters: Optional[List]=None) -> dict:
        try:
            return self.hapi_client.get_info(dataset, parameters)
        except (HapiRequestError, HapiServerError) as e:
            error_msg = _exception_to_error_message(e)
            return error_msg

    def data(self, dataset: str, start: str, stop: str,
             parameters: List[str] = None) -> Optional[SpeasyVariable]:
        try: 
            return self.hapi_client.get_data(dataset, start, stop, parameters)
        except (HapiRequestError, HapiServerError) as e:
            error_msg = _exception_to_error_message(e)
            return error_msg
