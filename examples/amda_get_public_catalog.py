import speasy as spz

# loop over catalogs and download
catalog_id = spz.amda.list_catalogs()[0]
catalog = spz.amda.get_catalog(catalog_id)
print(catalog.values)
