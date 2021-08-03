import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

# connect to AMDA
amda = AMDA()

# list catalog IDs
for cid in amda.list_catalogs():
    print(cid)

# timetable metadata
for cid in amda.catalog:
    print(amda.catalog[cid])
