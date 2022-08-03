from ..inventory import flat_inventories, ProviderInventory


class DataProvider:
    def __init__(self, provider_name, provider_alt_names=None):
        self.provider_name = provider_name
        self.provider_alt_names = provider_alt_names or []
        flat_inv = ProviderInventory()
        flat_inventories.__dict__[provider_name] = flat_inv
        for alt_name in self.provider_alt_names:
            flat_inventories.__dict__[alt_name] = flat_inv
