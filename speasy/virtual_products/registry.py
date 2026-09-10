"""Virtual products: products computed locally instead of fetched from a web service."""

from ..core.requests_scheduling.request_dispatch import PROVIDERS


class _VirtualProvider:
    """Serves virtual products through speasy's dispatch table.

    Deliberately not a DataProvider subclass: get_data() is the whole contract the
    dispatcher needs, while DataProvider.__init__ would fetch an inventory through
    the proxy for products that are local by definition.
    """

    def get_data(self, product_uid: str, start_time, stop_time, **kwargs):
        raise ValueError(f"Unknown virtual product 'virtual/{product_uid}'")


PROVIDERS['virtual'] = _VirtualProvider()
