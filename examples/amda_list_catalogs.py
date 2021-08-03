import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA
import datetime

amda = AMDA()
ttlist = amda.list_catalogs()
for catalog in amda.list_catalogs():
    print(catalog)
    print(amda.catalog[catalog])
    #print(amda.get_catalog(catalog).data)
