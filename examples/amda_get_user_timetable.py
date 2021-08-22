import speasy as spz


# get list of user timetables
for tt in spz.amda.list_user_timetables():
    print(spz.amda.get_user_timetable(tt["id"]))
