import speasy as spz
from datetime import datetime

start, stop = datetime(2000, 1, 1, 1), datetime(2000, 1, 1, 2)
for param in spz.amda.list_user_parameters():
    print(param)
    # get the parameter
    print(spz.amda.get_user_parameter(param, start, stop).data)
