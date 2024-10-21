from typing import Optional
from .codec_interface import CodecInterface
from speasy.config import core as cfg
import os
import appdirs

__USER_CODECS_DIR__ = f'{appdirs.user_data_dir("speasy", "LPP")}/codecs'

__CODECS__ = {}

"""Speasy codecs registry

This module provides a registry for codecs that can be used to load and save data from different formats. Codecs are registered by their name, supported extensions and supported mimetypes. The registry is used to find the codec that can handle a given file extension or mimetype. Codecs are registered using the `register_codec` decorator.
To register a codec, you must create a class that implements the `CodecInterface` interface and decorate it with the `register_codec` decorator. The codec class will be automatically instantiated and registered in the codecs registry when placed in the user codecs directory. The user codecs directory is defined by the `user_codecs_dir` function.
Alternatively, you can add custom lookup paths to the codecs registry by setting the `user_codecs_extra_dirs` configuration entry to a list of paths. Codecs placed in these paths will be automatically registered in the codecs registry too.
"""


def user_codecs_dir():
    """Get the user codecs directory, any codec placed in this directory will be automatically registered

    Returns
    -------
    str
        The user codecs directory
    """
    return __USER_CODECS_DIR__

def _register_codec(codec: CodecInterface):
    if codec.name in __CODECS__:
        raise ValueError(f"codec {codec.name} already registered")
    __CODECS__[codec.name] = codec
    for ext in codec.supported_extensions:
        if ext in __CODECS__:
            raise ValueError(f"A codec is already registered for extension {ext}")
        __CODECS__[ext] = codec
    for mime in codec.supported_mimetypes:
        if mime in __CODECS__:
            raise ValueError(f"A codec is already registered for mimetype {mime}")
        __CODECS__[mime] = codec


def register_codec(cls):
    """Decorator to register a codec in the codecs registry

    Parameters
    ----------
    cls : CodecInterface
        The codec class to register

    Returns
    -------
    CodecInterface
        The codec class that was registered
    """
    _register_codec(cls())
    return cls


def _list_dir_abs(path: str):
    return [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.py')]

def _load_codec(path: str):
    if path.endswith('.py'):
        exec(open(os.path.join(path, path)).read())


def load_extra_codecs():
    if os.path.exists(user_codecs_dir()):
        list(map(_load_codec, _list_dir_abs(user_codecs_dir())))
    for path in cfg.user_codecs_extra_dirs.get():
        if os.path.exists(path):
            list(map(_load_codec, _list_dir_abs(path)))


load_extra_codecs()


def get_codec(codec: str) -> Optional[CodecInterface]:
    """Get a codec by name, extension or mimetype

    Parameters
    ----------
    codec : str
        Codec name, extension or mimetype

    Returns
    -------
    Optional[CodecInterface]
        The codec that matches the given name, extension or mimetype, or None if no codec is found
    """
    return __CODECS__.get(codec, None)
