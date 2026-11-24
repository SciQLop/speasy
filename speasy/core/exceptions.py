"""Speasy's public exceptions, all derived from :class:`SpeasyError`.

Most also keep the built-in base they had before this module existed (``ValueError``, ``TypeError``, …), so code
catching those still works. They stay importable from the modules that raise them.
"""


class SpeasyError(Exception):
    """Base class of every exception Speasy raises on purpose."""


class UnknownProduct(SpeasyError, ValueError):
    """No provider knows this product id: a typo, a product removed upstream, or a disabled provider or server."""


class UnknownProvider(UnknownProduct):
    """The provider part of the id (``<provider>/...``) names no registered or enabled provider."""


class UnknownDataset(UnknownProduct):
    """The provider is known, the dataset id isn't."""


class UnknownParameter(UnknownProduct):
    """The provider is known, the parameter id isn't."""


class UnknownVirtualProduct(UnknownProduct):
    """Raised when a virtual product is requested but was never registered."""


class VirtualProductTypeError(SpeasyError, TypeError):
    """Raised when a virtual product callback returns something other than a SpeasyVariable or None."""


class VirtualProductCycleError(SpeasyError, RecursionError):
    """Raised when a virtual product requests itself, directly or through other virtual products."""


class TimeAxisMismatch(SpeasyError, ValueError):
    """Raised when operands with different time axes are combined without a directive."""


class NotStorable(SpeasyError, TypeError):
    """A value or product kind a data index doesn't know how to store; ``product`` is the product it came with."""

    def __init__(self, message: str, product=None):
        super().__init__(message)
        self.product = product


class ProxyError(SpeasyError):
    """The speasy-proxy server failed to answer a request; Speasy then asks the source itself."""


class TapError(SpeasyError):
    """A TAP (Table Access Protocol) query failed."""


class CdaWebException(SpeasyError):
    """CDAWeb's web service failed to answer a request."""


class Cdpp3dViewWebException(SpeasyError):
    """CDPP 3DView's web service failed to answer a request."""


class HapiError(SpeasyError):
    """Base class of the errors of a HAPI server."""


class HapiRequestError(HapiError):
    """4xx — Client Error (unknown dataset, bad date format, ...)"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class HapiServerError(HapiError):
    """5xx — Server Error"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class HapiNoData(HapiError):
    """1201 — Valid request, but no available data on time range"""


class HapiServerUnavailable(HapiError, ConnectionError):
    """The server, or the dataset needed, could not be loaded"""


class MissingCredentials(SpeasyError):
    """An AMDA (or other IMPEx) request needs a login, and none is configured."""


class InvalidCredentials(SpeasyError):
    """Kept for compatibility: Speasy doesn't raise it at the moment."""


class UnavailableEndpoint(SpeasyError):
    """The IMPEx server (AMDA, …) doesn't offer the web service endpoint a request needs."""


class BadTemplateArgDefinition(SpeasyError):
    """A templated parameter's arguments don't match its definition."""


class FailedChunkedRequest(SpeasyError):
    """At least one chunk of a request split in several failed."""
