import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

amda=AMDA()

for paramid in amda.list_parameters():
    print(amda.parameter[paramid])
    print([k for k in amda.parameter[paramid]])
