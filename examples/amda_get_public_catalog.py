import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

amda = AMDA()
print(amda.catalog)
for c in amda.catalog:
    print()
    print(c, amda.catalog[c])
    print(amda.get_catalog(c))
