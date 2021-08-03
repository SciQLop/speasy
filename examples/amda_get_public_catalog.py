import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

# connect to AMDA
amda = AMDA()

# loop over catalogs and download
catalog_id = amda.list_catalogs()[0]
catalog = amda.get_catalog(catalog_id)
print(catalog.values)
