from speasy.core.codecs.codecs_registry import register_codec

from ..codec import HapiBaseCodec
from .writer import save_hapi_binary
from .reader import load_hapi_binary


@register_codec
class HapiBinary(HapiBaseCodec):
    """Codec for HAPI Binary files"""
    def __init__(self):
        super().__init__(load_hapi_binary, save_hapi_binary)

    @property
    def name(self):
        return "hapi/binary"
