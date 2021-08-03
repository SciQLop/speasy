import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

# connect to AMDA
amda=AMDA()

# loop over user catalogs
for ucat in amda.list_user_catalogs():
    print(ucat)
