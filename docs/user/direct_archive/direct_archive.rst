Direct archive access
=====================

.. toctree::
   :maxdepth: 1

The Direct Archive Access module in Speasy enables users to access any local or remote data archive that stores data in
`ISTP <https://spdf.gsfc.nasa.gov/istp_guide/>`_ compliant `CDF <https://cdf.gsfc.nasa.gov/>`_ files. This module does not interact with any web service. Instead, it provides flexibility for users
to configure and populate the necessary configuration files to expose the desired products.

Using this module, Speasy can seamlessly retrieve data from the specified data archive, leveraging predictable file names
and paths within the archive. By adhering to the `ISTP <https://spdf.gsfc.nasa.gov/istp_guide/>`_  standards, Speasy
ensures compatibility and smooth data access.

This module supports both regularly split files (one file per day for example) and randomly split files such as burst data.

To add your favourite products into Speasy, you need to add or edit an yaml file either located in Speasy lookup
path, default user lookup path can be retrieved with ``spz.webservices.generic_archive.user_inventory_dir()``. You need to
add an entry per dataset with the following information:

- for a regularly split dataset:

.. code-block:: YAML

    tha_efi:
      inventory_path: cdpp/THEMIS/THA/L2
      master_cdf: http://cdpp.irap.omp.eu/themisdata/tha/l2/efi/0000/tha_l2_efi_00000000_v01.cdf
      split_frequency: daily
      split_rule: regular
      url_pattern: http://cdpp.irap.omp.eu/themisdata/tha/l2/efi/{Y}/tha_l2_efi_{Y}{M:02d}{D:02d}_v\d+.cdf
      use_file_list: true

Where:
    - **tha_efi** is the name you want to give to your dataset
    - **inventory_path:** is the inventory path you want for your dataset, in this example you will find it in ``spz.inventories.data_tree.archive.cdpp.THEMIS.THA.L2.tha_efi``
    - **master_cdf:** the URL or path to download a master CDF or any sample CDF for this dataset, Speasy needs it to complete the inventory with your dataset `data variables <https://spdf.gsfc.nasa.gov/istp_guide/variables.html#Data>`_. Prefer master CDFs over regular CDF since they have enough information while being smaller.
    - **split_frequency:** the split frequency of your dataset, for example if you have one file per day, month or year. Allowed values are *daily*, *monthly*, *yearly*
    - **url_pattern:** the URL pattern to access each file. When requesting some data in a given interval, Speasy will use the *split_frequency* to predict how many files needs be downloaded and substitute date/time information. It uses python *{}* format syntax and currently year **Y**, month **M** and day **D** are available. Python regular expressions are also supported in case you can't predict some part of the **file name** such as the file version but you have set *use_file_list* to true.
    - **use_file_list:** if true, once the URL generated from *url_pattern*, Speasy will list files in the given directory and then take the last file matching the file name in order to pick the latest version.
