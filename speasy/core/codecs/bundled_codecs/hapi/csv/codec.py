from speasy.core.codecs.codec_interface import Buffer
from speasy.core.codecs.codecs_registry import register_codec

from ..codec import HapiBaseCodec
from .reader import load_hapi_csv
from .writer import save_hapi_csv


@register_codec
class HapiCsv(HapiBaseCodec):
    def __init__(self):
        super().__init__(load_hapi_csv, save_hapi_csv)

    @property
    def name(self):
        return "hapi/csv"
