CDPP 3DView Data Provider
=========================

.. toctree::
   :maxdepth: 1


`CDPP 3DView <https://3dview.irap.omp.eu/>`_ provides planets, spacecrafts and comets trajectories in different
coordinate systems. Its integration into speasy makes easy to get trajectory data for various missions
on any time range.

Basics: Getting data from Cdpp3dView module
--------------------------------------------
All the trajectories available are discoverable using speasy dynamic inventory, they are organized by
mission/target/coordinate system:

    >>> import speasy as spz
    >>> trajectories = spz.inventories.tree.cdpp3dview.Trajectories
    >>> trajectories
    <SpeasyIndex: Trajectories>
    >>> mex_traj = spz.get_data(spz.inventories.tree.cdpp3dview.Trajectories.SPACECRAFT.MEX, "2010-01-02", "2010-01-03")
    >>> mex_traj
    <speasy.products.variable.SpeasyVariable object at ...>
    >>> mex_traj.shape
    (144, 3)
    >>> mex_traj.columns
    ['x', 'y', 'z']

    >>> # Optional parameters: coordinate_frame and sampling (in seconds)
    >>> mex_framed = spz.get_data(spz.inventories.tree.cdpp3dview.Trajectories.SPACECRAFT.MEX, "2010-01-02", "2010-01-03",
    ...                             coordinate_frame="ECLIPJ2000")
    >>> mex_framed
    <speasy.products.variable.SpeasyVariable object at ...>
    >>> mex_sampled = spz.get_data(spz.inventories.tree.cdpp3dview.Trajectories.SPACECRAFT.MEX, "2010-01-02", "2010-01-03",
    ...                                sampling="60")
    >>> mex_sampled
    <speasy.products.variable.SpeasyVariable object at ...>
