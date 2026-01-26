CDPP 3DView Data Provider
=========================

.. toctree::
   :maxdepth: 1


`CDPP 3DView <https://3dview.irap.omp.eu/>`_ provides planets, spacecrafts and comets trajectories in different 
coordinate systems. It's integration into speasy makes easy to get trajectory data for various missions 
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
    (1440, 3)
    >>> mex_traj.columns
    ['x', 'y', 'z']

    >>> # Optional parameters: coordinate_frame and sampling (in seconds)
    >>> mex_framed = spz.get_data(spz.inventories.tree.cdpp3dview.Trajectories.SPACECRAFT.MEX, "2010-01-02", "2010-01-03", 
    ...                             coordinate_frame="ECLIPJ2000")
    >>> mex_framed
    SpeasyVariable(
    Name: 'pos', 
    Time Range: 2010-01-02T00:00:00.000000000 - 2010-01-02T23:50:00.000000000
    Shape: (144, 3), 
    Unit: 'km', 
    Columns: ['x', 'y', 'z'], 
    Meta: {
        CATDESC: 'position in ECLIPJ2000 frame', 
        DISPLAY_TYPE: 'time_series', 
        FIELDNAM: 'Position', 
        UNITS: 'km', 
        VAR_TYPE: 'data', 
        DEPEND_0: 'Epoch', 
        LABL_PTR_1: ['x', 'y', 'z'], 
        }, 
    Size: '3.5 kB', 
    )
    >>> mex_sampled = spz.get_data(spz.inventories.tree.cdpp3dview.Trajectories.SPACECRAFT.MEX, "2010-01-02", "2010-01-03", 
    ...                                sampling="60")
    >>> mex_sampled
    SpeasyVariable(
    Name: 'pos', 
    Time Range: 2010-01-02T00:00:00.000000000 - 2010-01-02T23:59:00.000000000
    Shape: (1440, 3), 
    Unit: 'km', 
    Columns: ['x', 'y', 'z'], 
    Meta: {
        CATDESC: 'position in J2000 frame', 
        DISPLAY_TYPE: 'time_series', 
        FIELDNAM: 'Position', 
        UNITS: 'km', 
        VAR_TYPE: 'data', 
        DEPEND_0: 'Epoch', 
        LABL_PTR_1: ['x', 'y', 'z'], 
        }, 
    Size: '29.4 kB', 
    )
