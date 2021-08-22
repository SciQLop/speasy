import speasy as spz
from datetime import datetime

# get list of users parameters
parameter_list = spz.amda.list_user_parameters()

# get each parameter between the 1st and 2nd of January 2000
start, stop = datetime(2000, 1, 1), datetime(2000, 1, 2)
for param in parameter_list:
    print("Parameter id : {}".format(param["id"]))
    # download data
    p = spz.amda.get_user_parameter(param["id"], start, stop)
    print(p)
