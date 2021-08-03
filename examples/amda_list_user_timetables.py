import sys
sys.path.insert(0,"..")

from speasy.amda import AMDA

# connect to AMDA
amda=AMDA()

# loop over user timetables
for utt in amda.list_user_timetables():
    print(utt)
