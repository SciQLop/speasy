Data Providers
==============

.. toctree::
   :titlesonly:
   :hidden:
   :maxdepth: 2

   amda/amda
   sscweb/sscweb
   cdaweb/cdaweb
   csa/csa
   cdpp3dview/cdpp3dview
   direct_archive/direct_archive
   Uiowa_eph_tool/uiowa_eph_tool.rst

Speasy provides access to the following web services:

    - :doc:`Automated Multi-Dataset Analysis (AMDA) <amda/amda>` — parameters, catalogs, and timetables from the CDPP
    - :doc:`Coordinated Data Analysis Web (CDAWeb) <cdaweb/cdaweb>` — public heliophysics data from current and past missions
    - :doc:`Cluster Science Archive (CSA) <csa/csa>` — Cluster and Double Star mission data
    - :doc:`Satellite Situation Center Web (SSCWeb) <sscweb/sscweb>` — spacecraft and planet trajectories
    - :doc:`CDPP 3DView <cdpp3dview/cdpp3dview>` — planet, spacecraft, and comet trajectories in various coordinate systems (**disabled by default**, see its page)
    - :doc:`University of Iowa Cassini Ephemeris Tool (UiowaEphTool) <Uiowa_eph_tool/uiowa_eph_tool>` — Cassini, Ulysses, and Voyager trajectories

Speasy can also access data directly from local or remote archives using the :doc:`Direct Archive Access module <direct_archive/direct_archive>`.

While you can download any data with :meth:`speasy.get_data`, each web service has specificities and may expose extra
features through its dedicated module.

.. note::
    You can disable any provider by adding it to the ``disabled_providers`` list in your configuration file. See :ref:`disabling_providers`.

Discovering products: the inventory system
-------------------------------------------

Every provider builds a searchable **inventory** of the products it offers, exposed two ways:

- ``spz.inventories.tree.<provider>`` (or ``spz.inventories.data_tree.<provider>``) — a nested tree of
  :class:`~speasy.core.inventory.indexes.SpeasyIndex` objects you can browse with tab-completion in
  IPython/Jupyter (e.g. ``spz.inventories.tree.amda.Parameters.ACE.MFI``).
- ``spz.inventories.flat_inventories.<provider>`` — the same products as a flat, dict-like mapping keyed
  by product id, handy for programmatic lookup (``"ace" in spz.inventories.flat_inventories.ssc.parameters``).

Leaf index objects (e.g. a :class:`~speasy.core.inventory.indexes.ParameterIndex`) carry metadata as
attributes (``spz_uid``, ``spz_name``, ``spz_provider``, ...) and can be passed directly to
:meth:`speasy.get_data` instead of a string id. Inventories are rebuilt in the background and locally
cached; see ``inventories.cache_retention_days`` in :doc:`configuration` to control how often they refresh.

Product types: Variables, Catalogs, TimeTables, Events, and Datasets
-----------------------------------------------------------------------

Most calls to :meth:`speasy.get_data` return a :class:`~speasy.products.variable.SpeasyVariable` — a
single time series (see :doc:`numpy` and :doc:`scipy` for what you can do with one). A few other product
types exist for specific use cases:

- :class:`~speasy.products.catalog.Event` — a time interval (like a ``DateTimeRange``) with attached metadata.
- :class:`~speasy.products.catalog.Catalog` — an ordered collection of ``Event`` objects, e.g. all the
  intervals where a particular phenomenon was detected.
- :class:`~speasy.products.timetable.TimeTable` — an ordered collection of plain time intervals, commonly
  used to drive a batch fetch (pass a ``TimeTable`` as ``get_data()``'s time range to retrieve one
  variable for every interval at once).
- :class:`~speasy.products.dataset.Dataset` — a collection of ``SpeasyVariable`` objects for every
  parameter of an instrument/dataset, indexable by variable name (``dataset['b_gse']``).

Today, Catalogs, TimeTables, and Datasets are produced by the :doc:`AMDA module <amda/amda>`, which has a
full worked walkthrough including using a TimeTable to batch-fetch and analyze data — see its
:ref:`amda_catalogs_timetables` and :ref:`amda_datasets` sections.

.. _time_ranges:

Time ranges
-----------

``get_data()`` and similar calls accept ``start``/``stop`` as plain strings (e.g. ``"2016-6-2"`` or
``"2018-01-01T01:00:00"``), :class:`~datetime.datetime` objects, or :class:`numpy.datetime64` values.
String times are parsed as **UTC** — Speasy does not apply any local timezone conversion. Any precision
from whole days down to sub-second (e.g. ``"2018-01-01T01:00:00.123456"``) is accepted.

.. _coordinate_frames:

Coordinate frames
-----------------

Trajectory- and vector-valued products (e.g. from SSCWeb, CDAWeb, CSA, CDPP 3DView) are returned in
whichever coordinate frame the underlying archive stores them in, or in the frame you request via a
provider-specific keyword (e.g. ``coordinate_system``/``coordinate_frame``). Common frames you'll see
across provider pages:

.. list-table::
   :widths: 15 85
   :header-rows: 1

   * - Acronym
     - Meaning
   * - ``GEO``
     - Geographic — fixed to the rotating Earth.
   * - ``GEI``
     - Geocentric Equatorial Inertial — Earth-centered, fixed with respect to the stars (not rotating with Earth).
   * - ``GSE``
     - Geocentric Solar Ecliptic — X toward the Sun, Z normal to the ecliptic plane.
   * - ``GSM``
     - Geocentric Solar Magnetospheric — X toward the Sun, Z-X plane contains Earth's magnetic dipole axis.
   * - ``SM``
     - Solar Magnetic — Z along the dipole axis, Y perpendicular to the Sun-dipole plane.
   * - ``RTN``
     - Radial-Tangential-Normal — spacecraft-centered, R points away from the Sun; common for heliospheric missions.
   * - ``J2000`` / ``ECLIPJ2000``
     - Inertial frames referenced to the Earth's mean equator/equinox (``J2000``) or the ecliptic
       (``ECLIPJ2000``) at epoch J2000.0; used by CDPP 3DView.

Picking the wrong frame silently returns believable-looking but physically wrong vectors, so always check
which frame a provider page's examples request before comparing data across missions.

Units
-----

Speasy does not convert units: values and the ``UNITS`` metadata field are passed through exactly as
provided by the source service (AMDA, CDAWeb, ...). Check a variable's ``.unit`` attribute or its
``UNITS``/``CATDESC`` metadata to know what you're actually looking at.

When ``get_data()`` returns ``None`` vs. when it raises
---------------------------------------------------------

A **known** product (one Speasy's inventory recognizes) that has no data for the requested time range, or
whose request fails after retries, makes ``get_data()`` (and ``get_dataset()``/``get_catalog()``/``get_timetable()``)
return ``None`` — it does not raise. Always check for ``None`` before using the result:

.. code-block:: python

    import speasy as spz
    var = spz.get_data("amda/imf", "1900-01-01", "1900-01-02")  # valid product, no data that far back
    if var is None:
        print("No data returned — check the product id and time range")
    else:
        var.plot()

An **unrecognized** product id or inventory path, on the other hand, raises ``ValueError`` immediately
(Speasy can't even identify which provider/product to ask), and some providers raise a provider-specific
exception for certain invalid arguments (e.g. CDPP 3DView raises ``Cdpp3dViewWebException`` for an invalid
``coordinate_frame``):

.. code-block:: pycon

    >>> import speasy as spz
    >>> spz.get_data("amda/this_product_does_not_exist", "2018-01-01", "2018-01-02")
    Traceback (most recent call last):
        ...
    ValueError: Unknown product: this_product_does_not_exist

So a robust caller typically wants both: a ``try``/``except`` for the id lookup, and a ``None`` check for
the data itself.
