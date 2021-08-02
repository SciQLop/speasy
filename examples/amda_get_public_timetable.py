import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

amda = AMDA()

ttid = "sharedtimeTable_0"

timetable = amda.get_timetable(ttid)

print(timetable)
print("timetable id : {}".format(ttid))
print("time.shape   : {}".format(timetable.time.shape))
print("values.shape : {}".format(timetable.values.shape))
