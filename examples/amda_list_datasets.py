import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

amda=AMDA()
for cid in amda.list_datasets():
    print(amda.dataset[cid])
