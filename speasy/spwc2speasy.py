from spwc.common.variable import SpwcVariable
from spwc import cache as spwc_cache
import spwc.cache

import speasy.cache
from speasy.common.variable import SpeasyVariable
from speasy import cache as spz_cache


def spwc_2_speasy_variable(v: SpwcVariable) -> SpeasyVariable:
    return SpeasyVariable(time=v.time, data=v.data, meta=v.meta, columns=v.columns, y=v.y)


def spwc_2_speasy_cache_item(item: spwc.cache.CacheItem):
    return speasy.cache.CacheItem(spwc_2_speasy_variable(item.data), item.version)


for entry in spwc_cache.entries():
    item = spwc_cache.get_item(entry)
    if type(item) is spwc.cache.CacheItem:
        spz_cache.add_item(entry, spwc_2_speasy_cache_item(item))
