import os
import sys
sys.path.insert(0,"..")

from datetime import datetime

from speasy.amda import AMDA
from speasy.config import ConfigEntry

# set users credentials for AMDA
ConfigEntry("AMDA","username").set(os.environ["AMDA_USER"])
ConfigEntry("AMDA","password").set(os.environ["AMDA_PWD"])

# connect to AMDA
amda = AMDA()

# get list of users parameters
parameter_list = amda.list_user_parameters()

# get each parameter between the 1st and 2nd of January 2000
start, stop = datetime(2000,1,1), datetime(2000,1,2)
for param in parameter_list:
    print("Parameter id : {}".format(param["id"]))
    # download data
    p = amda.get_user_parameter(param["id"], start, stop)
    print(p)

