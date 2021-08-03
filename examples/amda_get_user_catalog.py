import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

# connect to AMDA
amda = AMDA()

# get list of user catalog
for tt in amda.list_user_catalogs():
    print(amda.get_user_catalog(tt["id"]))
