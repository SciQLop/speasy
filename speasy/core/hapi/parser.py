import io
from typing import List, Mapping
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.codecs.codecs_registry import get_codec
from speasy.core.hapi.exceptions import HapiError
from speasy.products.variable import SpeasyVariable


def _parse_hapi_csv(
    file: io.IOBase, parameters: List[str]
) -> Mapping[str, SpeasyVariable]:
    """Converts the CSV returned by /data into a SpeasyVariable.
    """
    if not parameters:
        raise HapiError(
            f"Wrong 'parameters' argument to hapi.load_variables: {parameters}"
        )
    hapi_csv_codec: CodecInterface = get_codec('hapi/csv')
    variables = hapi_csv_codec.load_variables(file=file, variables=parameters,
                                              disable_cache=True)
    return variables
