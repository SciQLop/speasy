from datetime import timedelta
import io
from typing import AnyStr, List, Mapping, Optional, Union


from speasy.core.cache._function_cache import CacheCall
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.codecs.codecs_registry import register_codec
from speasy.core.codecs.codec_interface import Buffer
from speasy.products.variable import SpeasyVariable


@register_codec
class HapiBinary(CodecInterface):
    """Codec for HAPI Binary files"""

    def load_variables(self, variables: List[AnyStr], file: Union[Buffer, str, io.IOBase], cache_remote_files=True,
                       **kwargs) -> Optional[Mapping[AnyStr, SpeasyVariable]]:
        # hapi_csv_file = load_hapi_binary(file)
        # if hapi_csv_file is not None:
        #     return _hapi_csv_to_speasy_variables(hapi_csv_file, variables)
        return None

    @CacheCall(cache_retention=timedelta(seconds=120), is_pure=True)
    def load_variable(self,
                      variable: AnyStr, file: Union[Buffer, str, io.IOBase],
                      cache_remote_files=True,
                      **kwargs
                      ) -> Optional[SpeasyVariable]:
        return self.load_variables([variable], file, cache_remote_files)[variable]

    def save_variables(self,
                       variables: List[SpeasyVariable],
                       file: Optional[Union[str, io.IOBase]] = None,
                       **kwargs
                       ) -> Union[bool, Buffer]:
        # hapi_csv_file = _speasy_variables_to_hapi_csv(variables)
        # return save_hapi_csv(hapi_csv_file, file)
        return True

    @property
    def supported_extensions(self) -> List[str]:
        return []

    @property
    def supported_mimetypes(self) -> List[str]:
        return []

    @property
    def name(self) -> str:
        return "hapi/binary"
