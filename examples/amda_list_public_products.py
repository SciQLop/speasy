import speasy as spz

# get list of datasets
datasets = spz.amda.list_datasets()

# get parameter list
parameters = spz.amda.list_parameters()

# get time-table list
timetables = spz.amda.list_timetables()

print("AMDA_Webservice products")
print("\tDatasets   : {}".format(len(datasets)))
print("\tParameters : {}".format(len(parameters)))
print("\tTimetables : {}".format(len(timetables)))
