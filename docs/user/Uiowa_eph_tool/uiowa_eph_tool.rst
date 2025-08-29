University of Iowa Cassini Ephemeris Tool
=========================================

.. toctree::
   :maxdepth: 1


`UiowaEphTool <https://space.physics.uiowa.edu/~jbg/cas.html>`_ provides trajectories for Cassini, Ulysses, Voyager 1 and Voyager 2 spacecrafts
in different coordinate systems. It's integration into speasy makes easy to get any available object trajectory on any time range.

Basics: Getting data from UiowaEphTool module
---------------------------------------------
All the trajectories available are discoverable using speasy dynamic inventory, they are organized by origin/coordinate system/object:

    >>> import speasy as spz
    >>> trajectories = spz.inventories.tree.uiowaephtool.Trajectories
    >>> cassini_traj=spz.get_data(trajectories.Callisto.Co_rotational.Cassini, "2010-01-02", "2010-01-03")
    >>> cassini_traj
    SpeasyVariable(
        Name: 'Cassini',
        Time Range: 2010-01-02T00:00:00.000000000 - 2010-01-02T23:59:00.000000000
        Shape: (1440, 3),
        Unit: ('Rc', 'Rc', 'Rc'),
        Columns: ['X', 'Y', 'Z'],
        Meta: {
            UNITS: ('Rc', 'Rc', 'Rc'),
            COORDINATE_SYSTEM: 'Co-rotational',
            ORIGIN: 'Callisto',
            ORIGIN_RADIUS: '2410.3 km',
            OBSERVER: 'Cassini',
            DESCRIPTION: 'Trajectory of Cassini in Co-rotational coordinates centered on Callisto',
            FILE_HEADER: '                                                         Co-rotational Coordinate System\n\n                         +----------- Position (1 Rc = 2410.3 km) ----------+    +-------------------- Velocity --------------------+\n\n      SCET (UT)              X (Rc)        Y (Rc)        Z (Rc)        R (Rc)      X (km/s)      Y (km/s)      Z (km/s)   Vmag (km/s)\n---------------------    ----------    ----------    ----------    ----------    ----------    ----------    ----------   -----------',
            },
        Size: '46.5 kB',
        )

