import speasy as spz

ttid = "sharedtimeTable_0"

timetable = spz.amda.get_timetable(ttid)

print(timetable)
print("timetable id : {}".format(ttid))
print("time.shape   : {}".format(timetable.time.shape))
print("values.shape : {}".format(timetable.values.shape))
