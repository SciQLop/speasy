CDPP 3DView Data Provider
=========================

.. toctree::
   :maxdepth: 1


`CDPP 3DView <https://3dview.irap.omp.eu/>`_ (Centre de Données de la Physique des Plasmas 3DView) provides
planet, spacecraft, and comet trajectories, each available in a choice of coordinate frames. Its
integration into Speasy makes it easy to get trajectory data for various missions on any time range.

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
than from Speasy, so this is always the authoritative check:

    >>> frames = spz.cdpp3dview.get_frames()
    >>> 'ECLIPJ2000' in frames
    True

Passing a frame the server doesn't know raises
:class:`~speasy.data_providers.cdpp3dview.Cdpp3dViewWebException`, and the message lists the frames that
are available.

**At the time of writing** the server offered these 106 frames, grouped by the body they're centred on:

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Body
     - Frames
   * - Sun / heliosphere
     - ``J2000``, ``ECLIPJ2000``, ``HEE``, ``HEEQ``, ``HCI``, ``IAU_SUN``
   * - Mercury
     - ``MESO``, ``MEME``, ``MECLIP``, ``MESE``, ``MESEQ``, ``IAU_MERCURY``
   * - Venus
     - ``VSO``, ``VME``, ``IAU_VENUS``
   * - Earth
     - ``GSE``, ``EME``, ``GSEQ``, ``ECLIPDATE``, ``MAG``, ``GSM``, ``SM``, ``IAU_EARTH``
   * - Moon
     - ``LSE``, ``LME``, ``IAU_MOON``
   * - Mars
     - ``MSO``, ``MME``, ``IAU_MARS``
   * - Phobos
     - ``PSE``, ``PME``
   * - Deimos
     - ``DSE``, ``DME``
   * - Jupiter
     - ``JSO``, ``JEME``, ``JECLIP``, ``JSM``, ``SYSTEM_3``, ``IAU_JUPITER``
   * - Io, Europa, Ganymede, Callisto
     - ``IPHIO``, ``EPHIO``, ``GPHIO``, ``CPHIO`` (respectively)
   * - Saturn
     - ``KSO``, ``KEME``, ``KECLIP``, ``KSM``, ``IAU_SATURN``
   * - Mimas
     - ``KMIEME``, ``KMIECLIP``, ``MIIS``
   * - Enceladus
     - ``KENEME``, ``KENECLIP``, ``ENIS``
   * - Tethys
     - ``KTEEME``, ``KTEECLIP``, ``TEIS``
   * - Dione
     - ``KDIEME``, ``KDIECLIP``, ``DIIS``
   * - Rhea
     - ``KRHEME``, ``KRHECLIP``, ``RHIS``
   * - Titan
     - ``KTIEME``, ``KTIECLIP``, ``TIIS``
   * - Hyperion
     - ``KHYEME``, ``KHYECLIP``, ``HYIS``
   * - Iapetus
     - ``KIAEME``, ``KIAECLIP``, ``IAIS``
   * - Phoebe
     - ``KPHEME``, ``KPHECLIP``, ``PHIS``
   * - Two further Saturnian moons
     - ``KHEEME``, ``KHEECLIP``, ``HEIS``, ``KTLEME``, ``KTLECLIP``, ``TLIS``
   * - Uranus
     - ``UEME``, ``UECLIP``, ``USO``, ``IAU_URANUS``
   * - Neptune
     - ``NEME``, ``NECLIP``, ``NSO``, ``IAU_NEPTUNE``
   * - Pluto
     - ``PEME``, ``PECLIP``, ``PSO``, ``IAU_PLUTO``
   * - Comet 67P/Churyumov–Gerasimenko
     - ``67PCG_EME``, ``67PCG_CSO``
   * - Asteroid Lutetia
     - ``LUTETIA_EME``, ``LUTETIA_CSO``
   * - Asteroid Šteins
     - ``STEINS_EME``, ``STEINS_CSO``
   * - Comet Halley
     - ``HALLEY_EME``, ``HALLEY_CSO``
   * - Comet Grigg–Skjellerup
     - ``GRIGGSKELL_EME``, ``GRIGGSKELL_CSO``
   * - Asteroid Didymos
     - ``IAU_DIDYMOS``, ``DIDYMOS_EME``, ``DIDYMOS_CSO``

The naming follows a consistent pattern across bodies, so you can usually guess an unfamiliar one:

- ``IAU_<body>`` — body-fixed frame (rotates with the body), as defined by the IAU.
- ``<X>SO`` — "X Solar Orbital": a GSE-style, Sun-body-line frame generalized to body X.
- ``<X>SM`` — "X Solar Magnetic": like ``SM``/``GSM``, referenced to body X's magnetic dipole
  (only defined for the magnetized planets: Earth, Jupiter, Saturn).
- ``<X>ECLIP`` / ``<X>EME`` — inertial frames centred on body X, referenced to the ecliptic or to
  Earth's mean equator/equinox (the same convention as ``ECLIPJ2000``/``J2000``) respectively.
- ``<X>CSO`` — the comet/asteroid equivalent of the ``SO`` frames.
