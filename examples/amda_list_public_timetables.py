import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

amda = AMDA()

for ttid in amda.list_timetables():
    print(ttid)


for ttid in amda.timetable:
    print(amda.timetable[ttid])
