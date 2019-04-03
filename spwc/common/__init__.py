import diskcache as dc
from appdirs import *

cache = dc.Cache(user_cache_dir("SciQLop", "LPP"))


def get_cache_entries(server, product_name, start_date, stop_date):
    pass


def add_cache_entry(server, product_name, dataframe):
    pass


def listify(obj: list or object) -> list:
    if type(obj) is list:
        return obj
    else:
        return [obj]
