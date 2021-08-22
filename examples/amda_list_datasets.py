import speasy as spz

for cid in spz.amda.list_datasets():
    print(spz.amda.dataset[cid])
