import speasy as spz

for timetable in spz.amda.list_timetables():
    print(timetable)
    print(spz.amda.get_timetable(timetable))
