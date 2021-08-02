import sys
sys.path.insert(0,"..")
from speasy.amda import AMDA
import datetime

amda = AMDA()
ttlist = amda.list_timetables()
for timetable in amda.list_timetables():
    print(timetable)
    print(amda.get_timetable(timetable).data)
