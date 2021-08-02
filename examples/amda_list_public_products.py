import sys
sys.path.insert(0,"..")
from speasy.amda import AMDA
from datetime import datetime

amda = AMDA()

# get list of datasets
datasets = amda.list_datasets()

# get parameter list
parameters = amda.list_parameters()

# get time-table list
timetables = amda.list_timetables()

print("AMDA products")
print("\tDatasets   : {}".format(len(datasets)))
print("\tParameters : {}".format(len(parameters)))
print("\tTimetables : {}".format(len(timetables)))
