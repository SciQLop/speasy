CDPP 3DView Data Provider
=========================

.. toctree::
   :maxdepth: 1


`CDPP 3DView <https://3dview.irap.omp.eu/>`_ (Centre de Données de la Physique des Plasmas 3DView) provides
planet, spacecraft, and comet trajectories in different coordinate systems. Its integration into Speasy makes
it easy to get trajectory data for various missions on any time range.

.. note::
    This provider ships **disabled by default** (its web service has known issues that are still being
    addressed). Re-enable it by removing ``cdpp3dview`` from ``disabled_providers``, see :ref:`disabling_providers`.

Basics: Getting data from Cdpp3dView module
--------------------------------------------
All the trajectories available are discoverable using speasy dynamic inventory, they are organized by
body type then body name (e.g. ``Trajectories.SPACECRAFT.MEX``); the coordinate frame is not part of the
inventory tree, it's a keyword argument to ``get_data()`` (see ``coordinate_frame`` below, default ``J2000``):

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

Coordinate frames
-----------------

3DView supports far more frames than the other providers, and the list comes from the server rather
than from Speasy, so ask it directly rather than relying on any list written down here:

    >>> frames = spz.cdpp3dview.get_frames()
    >>> 'ECLIPJ2000' in frames
    True

Passing a frame the server doesn't know raises
:class:`~speasy.data_providers.cdpp3dview.Cdpp3dViewWebException`, and the message lists the frames that
are available.

At the time of writing the server offered 106 frames, covering the Sun and the heliosphere (``HEE``,
``HEEQ``, ``HCI``), the inertial frames (``J2000``, ``ECLIPJ2000``), the near-Earth frames (``GSE``,
``GSM``, ``SM``, ``MAG``, ``GSEQ``), one solar-orbital and one body-fixed frame per planet (``MSO`` and
``IAU_MARS`` for Mars, ``JSO`` and ``IAU_JUPITER`` for Jupiter, and so on), frames centred on the major
moons, and frames for the comets and asteroids visited by spacecraft (``67PCG_CSO``, ``DIDYMOS_CSO``, ...).
