from .codec_interface import CodecInterface, Buffer
from .codecs_registry import register_codec, get_codec, user_codecs_dir, load_extra_codecs

__all__ = ['CodecInterface', 'register_codec', 'get_codec', 'user_codecs_dir']

from . import bundled_codecs
from ..plugins import load_plugins

load_extra_codecs()
load_plugins("speasy.codecs")
