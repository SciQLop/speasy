import speasy as spz
from datetime import datetime

# define the parameter and dataset IDs and the data begining and end dates
parameter_id = "imf"
dataset_id = "ace-imf-all"
start, stop = datetime(2000, 1, 1), datetime(2000, 1, 2)

# get some information about the data time range
print("Parameter time range : {}".format(spz.amda.parameter_range(parameter_id)))
print("Dataset time range   : {}".format(spz.amda.parameter_range(dataset_id)))

# list parameters in dataset
print("Dataset parameters : {}".format(spz.amda.list_parameters(dataset_id=dataset_id)))

# download dataset contents, a list of SpeasyVariable objects
dataset = spz.amda.get_dataset(dataset_id, start, stop)
print(dataset)

# download parameter
param = spz.amda.get_parameter(parameter_id, start, stop)
print("Parameter : {}".format(param))
