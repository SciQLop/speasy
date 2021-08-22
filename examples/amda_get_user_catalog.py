import speasy as spz

# get list of user catalog
for tt in spz.amda.list_user_catalogs():
    print(spz.amda.get_user_catalog(tt["id"]))
