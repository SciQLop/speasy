Coordinated Data Analysis Web (CDAWeb)
======================================

.. toctree::
   :maxdepth: 1

The `Coordinated Data Analysis Web (CDAWeb) <https://cdaweb.gsfc.nasa.gov/>`__ contains selected public non-solar heliophysics
data from current and past heliophysics missions and projects. Many datasets from current missions are updated regularly
(even daily), including reprocessing older time periods, and SPDF only preserves the latest version.

Basics: Getting data from CDA module
------------------------------------

The easiest solution is to use your python terminal completion and browse `spz.inventories.data_tree.cda` to find
your product.
Once you have found your product, then simply ask CDA module to get data for the provided time range:

    >>> import speasy as spz
    >>> # Let's assume you wanted to get Solar Orbiter 'Magnetic field vector in RTN coordinates'
    >>> solo_mag_rtn = spz.get_data(spz.inventories.tree.cda.Solar_Orbiter.SOLO.MAG.SOLO_L2_MAG_RTN_NORMAL_1_MINUTE.B_RTN, "2021-01-01", "2021-01-02")
    >>> solo_mag_rtn.columns
    ['B_r', 'B_t', 'B_n']
    >>> solo_mag_rtn.values.shape
    (1438, 3)

Specific CDAWeb options
-----------------------

The CDAWeb module allows to choose the method to get data among 'BEST', 'FILE', 'API', default is 'BEST'.

* 'BEST' will try to choose the best method between 'FILE' and 'API' for each dataset.
* 'FILE' will download the data files from the CDAWeb server directly using the `archive` module.
* 'API' will get the data using the CDAWeb API.

User can specify the method to use to get the data by passing the `method` argument to the `spz.get_data` function.

    >>> import speasy as spz
    >>> # Let's assume you wanted to get Solar Orbiter 'Magnetic field vector in RTN coordinates'
    >>> solo_mag_rtn = spz.get_data(spz.inventories.tree.cda.Solar_Orbiter.SOLO.MAG.SOLO_L2_MAG_RTN_NORMAL_1_MINUTE.B_RTN, "2021-01-01", "2021-01-02", method='API')
    >>> solo_mag_rtn.columns
    ['B_r', 'B_t', 'B_n']
    >>> solo_mag_rtn.values.shape
    (1438, 3)

User can also set the default method to use to get the data by setting the `spz.config.cdaweb.preferred_access_method` configuration variable.

    >>> import speasy as spz
    >>> spz.config.cdaweb.preferred_access_method.set('BEST')
