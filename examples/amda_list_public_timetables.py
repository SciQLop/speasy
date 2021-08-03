import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

# connect to AMDA
amda = AMDA()

# list timetable IDs
for ttid in amda.list_timetables():
    print(ttid)

# timetable metadata
for ttid in amda.timetable:
    print(amda.timetable[ttid])
