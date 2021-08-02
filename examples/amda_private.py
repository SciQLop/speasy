import sys
sys.path.insert(0,"..")

import speasy
from speasy.config import ConfigEntry
from speasy.amda import AMDA

#amda_user = ConfigEntry("AMDA", "username").set("user")
#amda_pwd  = ConfigEntry("AMDA", "password").set("sirapass")

amda      = AMDA()

for param in amda.list_user_parameters():
    print(param)
    # get the parameter
    print(amda.get_user_parameter(param["id"]).data)
