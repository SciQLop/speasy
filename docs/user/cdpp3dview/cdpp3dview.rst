CDPP 3DView Data Provider
=========================

.. toctree::
   :maxdepth: 1


`CDPP 3DView <https://3dview.irap.omp.eu/>`_ (Centre de Données de la Physique des Plasmas 3DView) provides
planet, spacecraft, and comet trajectories, each available in a choice of coordinate frames. Its
integration into Speasy makes it easy to get trajectory data for various missions on any time range.

.. note::
    This provider is **enabled by default** as of speasy 1.8. It previously shipped disabled while its web
    service had known issues; those are now mostly resolved, and broader use helps surface what's left. If
    you hit problems, you can disable it again via ``disabled_providers``, see :ref:`disabling_providers`.

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
than from Speasy, so this is always the authoritative check:

    >>> frames = spz.cdpp3dview.get_frames()
    >>> 'ECLIPJ2000' in frames
    True

Passing a frame the server doesn't know raises
:class:`~speasy.data_providers.cdpp3dview.Cdpp3dViewWebException`, and the message lists the frames that
are available.

.. note::
    ``coordinate_system`` (the kwarg name used by the SSCWeb provider) is accepted as an alias for
    ``coordinate_frame`` here too, so switching between SSCWeb and 3DView doesn't require renaming
    a kwarg. Passing both with different values raises
    :class:`~speasy.data_providers.cdpp3dview.Cdpp3dViewWebException` rather than silently picking one.
    UiowaEphTool has no such kwarg at all — its coordinate system is chosen by browsing the
    inventory tree instead, see :doc:`its own page <../Uiowa_eph_tool/uiowa_eph_tool>`.

The table below is generated automatically from the server every time these docs are built, so it needs
no manual updates and cannot go stale the way a hand-written list would. If the server couldn't be
reached during the build, a note below says so and a cached snapshot is shown instead:

.. include:: _generated_frames_table.rst

The naming follows a consistent pattern across bodies, so you can usually guess an unfamiliar one:

- ``IAU_<body>`` — body-fixed frame (rotates with the body), as defined by the IAU.
- ``<X>SO`` — "X Solar Orbital": a GSE-style, Sun-body-line frame generalized to body X.

  .. warning::
      Guessing ``<X>SO`` frames has a collision: Mars is ``MSO`` but Mercury is ``MESO``
      (and the Moon has no ``SO`` frame at all). A wrong guess that happens to be a real
      frame yields perfectly valid data for the *wrong* planet, with no error — when in
      doubt, check the table above.
- ``<X>SM`` — "X Solar Magnetic": like ``SM``/``GSM``, referenced to body X's magnetic dipole
  (in 3DView's frame list, only defined for three of the solar system's magnetized planets:
  Earth, Jupiter, Saturn). For Earth specifically,
  the ``SM``/``GSM``/``MAG`` frames are not valid after 31/12/2014, as the generated table
  above mentions; the table is the authoritative check for other bodies.
- ``<X>ECLIP`` / ``<X>EME`` — inertial frames centred on body X, referenced to the ecliptic or to
  Earth's mean equator/equinox (the same convention as ``ECLIPJ2000``/``J2000``) respectively.
- ``<BODY>_CSO`` / ``<BODY>_EME`` — the comet/asteroid equivalents of the ``SO`` and
  ``EME`` frames, spelled with the full body name as a suffix: ``67PCG_CSO``,
  ``LUTETIA_CSO``, ``HALLEY_CSO``, ``67PCG_EME``, ...

``get_data()`` also accepts ``if_newer_than=...`` to only fetch data newer than a given
timestamp (it sends an ``If-Modified-Since`` header to the server).
