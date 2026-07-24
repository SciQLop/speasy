Satellite Situation Center (SSCWeb)
===================================

.. toctree::
   :maxdepth: 1


`SSCWeb <https://sscweb.gsfc.nasa.gov/>`_ provides trajectories for solar system objects such as planets, moons, and spacecraft
in different coordinate systems. Its integration into Speasy makes it easy to get any available trajectory for any time range.

Basics: Getting data from SSCWeb module
---------------------------------------

First, check that the trajectory you want is available. The easiest way is to browse
Speasy's dynamic inventory, which is always up to date:

    >>> import speasy as spz
    >>> ssc_trajectories = spz.inventories.flat_inventories.ssc.parameters
    >>> # hundreds of spacecraft are available, keyed by their id
    >>> 'ace' in ssc_trajectories
    True
    >>> len(ssc_trajectories) > 100
    True

Note that you can also use your python terminal completion and browse `spz.inventories.data_tree.ssc.Trajectories` to find
your trajectory.
Once you have found your trajectory, you can choose the coordinate system for the download.
The default is **gse**.

    >>> import speasy as spz
    >>> # Let's assume you wanted to get MMS1 trajectory
    >>> mms1_traj = spz.ssc.get_data(spz.inventories.data_tree.ssc.Trajectories.mms1, "2018-01-01", "2018-02-01", 'gsm')
    >>> mms1_traj.columns
    ['X', 'Y', 'Z']
    >>> mms1_traj.values
    array([[57765.7789, 39928.6469, 36127.6976],
           [57636.7873, 39912.6769, 36075.1812],
           [57507.6709, 39896.6512, 36022.4395],
           ...,
           [74135.0437,   741.7233, 27240.7339],
           [74007.2467,   795.057 , 27220.3705],
           [73879.1839,   848.3518, 27199.876 ]], shape=(44640, 3))

Coordinate systems
------------------

Pass one of these as the ``coordinate_system`` argument. The frame the service actually returned is
also echoed back in the variable's metadata, which is the reliable way to check what you got:

    >>> mms1_traj.meta['CoordinateSystem']
    'GSM'

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Value
     - Coordinate system
   * - ``geo``
     - Geographic: Z along the Earth's rotation axis, X in the equatorial plane through the Greenwich meridian. Rotates with the Earth.
   * - ``gm``
     - Geomagnetic: Z along the Earth's magnetic dipole axis, X in the plane containing the dipole and rotation axes.
   * - ``gse``
     - Geocentric Solar Ecliptic: X towards the Sun, Z normal to the ecliptic plane (default).
   * - ``gsm``
     - Geocentric Solar Magnetospheric: X towards the Sun, the X-Z plane containing the magnetic dipole axis.
   * - ``sm``
     - Solar Magnetic: Z along the magnetic dipole axis, Y perpendicular to the plane containing the dipole axis and the Earth-Sun line.
   * - ``geitod``
     - Geocentric Equatorial Inertial, true of date: X towards the vernal equinox and Z along the rotation axis, both at the date of the data.
   * - ``geij2000``
     - Geocentric Equatorial Inertial, referred to the mean equator and equinox of epoch J2000.0.

.. note::
    This list reflects what `SSCWeb <https://sscweb.gsfc.nasa.gov/>`_ offered at the time of writing and
    may not be up to date. See the `SSCWeb documentation <https://sscweb.gsfc.nasa.gov/users_guide/Appendix_C.shtml>`_
    for the authoritative list and the precise definitions.


