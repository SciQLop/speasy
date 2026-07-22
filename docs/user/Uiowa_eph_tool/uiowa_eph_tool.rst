University of Iowa Cassini Ephemeris Tool
=========================================

.. toctree::
   :maxdepth: 1


`UiowaEphTool <https://space.physics.uiowa.edu/~jbg/cas.html>`_ provides trajectories for Cassini, Ulysses, Voyager 1, and Voyager 2
in different coordinate systems. Its integration into Speasy makes it easy to get any available trajectory for any time range.

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

Coordinate systems
------------------

Here the coordinate system is the middle level of the inventory tree rather than an argument, so you
select it by browsing to it, and the systems on offer depend on the origin body:

    >>> sorted(k for k in trajectories.Callisto.__dict__ if not k.startswith(('_', 'spz')))
    ['Co_rotational', 'Ecliptic', 'Equatorial', 'Geographic', 'Id', 'Radius']

At the time of writing the tool offered five coordinate systems across 24 origin bodies: ``Ecliptic``
and ``Equatorial`` (available for every body), ``Geographic``, ``Co_rotational`` (for the planets and
moons with a defined rotation), and ``KSM`` (Saturn only). ``Id`` and ``Radius`` in the listing above
are body properties, not coordinate systems.
