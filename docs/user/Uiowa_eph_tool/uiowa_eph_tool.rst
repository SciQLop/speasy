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
    <speasy.products.variable.SpeasyVariable object at ...>
    >>> cassini_traj.shape
    (1440, 3)
    >>> cassini_traj.columns
    ['X', 'Y', 'Z']

