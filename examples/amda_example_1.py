import sys
sys.path.insert(0,"..")
from speasy.amda import AMDA
import datetime

amda = AMDA()

parameter_id="imf"
dataset_id="ace-imf-all"
start=datetime.datetime(2000,1,1)
stop = datetime.datetime(2000,2,1)

print("parameter time range : {}".format(amda.parameter_range(parameter_id)))
print("dataset time range   : {}".format(amda.parameter_range(dataset_id)))

print("Dataset parameters : {}".format(amda.list_parameters(dataset_id=dataset_id)))
dataset = amda.get_dataset(dataset_id, start, stop)
print(dataset)
for param in dataset:
    print(param)

# time table
ttid="sharedtimeTable_0"
tt=amda.get_timetable(ttid)
