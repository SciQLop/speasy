from types import SimpleNamespace


def empty_amda_inventory():
    return SimpleNamespace(
        TimeTables=SimpleNamespace(MyTimeTables=SimpleNamespace(), SharedTimeTables=SimpleNamespace()),
        Catalogs=SimpleNamespace(MyCatalogs=SimpleNamespace(), SharedCatalogs=SimpleNamespace()),
        DerivedParameters=SimpleNamespace(),
        Parameters=SimpleNamespace())

def empty_ssc_inventory():
    return SimpleNamespace(Trajectories=SimpleNamespace())



amda = empty_amda_inventory()
ssc = empty_ssc_inventory()


def reset_amda_inventory():
    amda = empty_amda_inventory()
