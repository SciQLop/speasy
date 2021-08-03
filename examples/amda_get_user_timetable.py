import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

# connect to AMDA
amda = AMDA()

# get list of user timetables
for tt in amda.list_user_timetables():
    print(amda.get_user_timetable(tt["id"]))
