from typing import Optional
from speasy.products.variable import SpeasyVariable


class HapiParser:

    @staticmethod
    def csv_to_variable(raw: bytes) -> Optional[SpeasyVariable]:
        """Converts the CSV returned by /data into a SpeasyVariable.
        """
        ...
