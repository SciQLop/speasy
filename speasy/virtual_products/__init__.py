"""Locally computed products, served through speasy's usual dispatch."""

# Importing the registry is what registers the 'virtual' provider.
from . import registry  # noqa: F401
from .registry import register_virtual_product  # noqa: F401
from .registry import UnknownVirtualProduct, VirtualProductCycleError, VirtualProductTypeError  # noqa: F401

from ..core.plugins import load_plugins

load_plugins("speasy.virtual_products")
