from typing import Optional
from speasy.products.variable import SpeasyVariable


class HapiParser:

    @staticmethod
    def csv_to_variable(raw: bytes, info: dict) -> Optional[SpeasyVariable]:
        """Convertit le CSV retourné par /data en SpeasyVariable.
        
        info est le dict retourné par /info (contient les métadonnées des paramètres).
        """
        ...
