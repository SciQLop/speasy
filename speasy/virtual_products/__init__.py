"""Locally computed products, served through speasy's usual dispatch."""

# Importing the registry is what registers the 'virtual' provider.
from . import registry  # noqa: F401
from .registry import UnknownVirtualProduct, VirtualProductTypeError, register_virtual_product  # noqa: F401
