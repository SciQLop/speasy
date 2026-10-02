from types import SimpleNamespace
from speasy.core.inventory import FlatInventories


def _provider_inventory(namespace, name):
    # A provider fills its inventory when initialized, which may not have happened yet
    # if SPEASY_SKIP_INIT_PROVIDERS is set.
    if not name.startswith('_'):
        from speasy.core.requests_scheduling.request_dispatch import _ensure_provider
        _ensure_provider(name)
        if name in namespace.__dict__:
            return namespace.__dict__[name]
    raise AttributeError(name)


def _provider_dir(namespace):
    from speasy.core.requests_scheduling.request_dispatch import _enabled_provider_names
    return sorted(set(object.__dir__(namespace)) | set(_enabled_provider_names()))


class _LazyTree(SimpleNamespace):
    __getattr__ = _provider_inventory
    __dir__ = _provider_dir


class _LazyFlatInventories(FlatInventories):
    __getattr__ = _provider_inventory
    __dir__ = _provider_dir


flat_inventories = _LazyFlatInventories()
tree = _LazyTree()
data_tree = tree
