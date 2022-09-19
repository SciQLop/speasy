Coordinated Data Analysis Web (CDAWeb)
======================================

.. toctree::
   :maxdepth: 1

The `Coordinated Data Analysis Web (CDAWeb) <https://cdaweb.gsfc.nasa.gov/>`_ contains selected public non-solar heliophysics
data from current and past heliophysics missions and projects. Many datasets from current missions are updated regularly
(even daily), including reprocessing older time periods, and SPDF only preserves the latest version.

Basics: Getting data from CDA module
------------------------------------

The easiest solution is to use your python terminal completion and browse `spz.inventories.data_tree.cda` to find
your product.
Once you have found your product, then simply ask CDA module to get data for the provided time range:

    >>> import speasy as spz
    >>> # Let's assume you wanted to get Solar Orbiter 'Magnetic field vector in RTN coordinates'
    >>> solo_mag_rtn = spz.cda.get_data(spz.inventories.tree.cda.Solar_Orbiter.SOLO.MAG.SOLO_L2_MAG_RTN_NORMAL_1_MINUTE.B_RTN, "2021-01-01", "2021-01-02")
    >>> solo_mag_rtn.columns
    ['B_r', 'B_t', 'B_n']
    >>> solo_mag_rtn.values.shape
    (1439, 3)
