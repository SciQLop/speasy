Speasy concepts
===============

.. toctree::
   :maxdepth: 1

The inventory
-------------

Every provider builds a searchable **inventory** of the products it offers, exposed two ways:

- ``spz.inventories.tree.<provider>`` (or ``spz.inventories.data_tree.<provider>``) — a nested tree of
  :class:`~speasy.core.inventory.indexes.SpeasyIndex` objects you can browse with tab-completion in
  IPython/Jupyter (e.g. ``spz.inventories.tree.amda.Parameters.ACE.MFI``).
- ``spz.inventories.flat_inventories.<provider>`` — the same products as a flat, dict-like mapping keyed
  by product id, handy for programmatic lookup (``"ace" in spz.inventories.flat_inventories.ssc.parameters``).

Finding products is easiest interactively — browse the tree with tab-completion until you reach the
product you want — while scripts usually look ids up in the flat inventories:

.. code-block:: python

    import speasy as spz
    # interactive browsing: spz.inventories.tree.amda.Parameters.ACE.<TAB>
    mfi = spz.inventories.tree.amda.Parameters.ACE.MFI
    # programmatic lookup by id (bare id, no provider prefix):
    "imf" in spz.inventories.flat_inventories.amda.parameters

Leaf index objects (e.g. a :class:`~speasy.core.inventory.indexes.ParameterIndex`) can be passed directly
to :func:`speasy.get_data` instead of a string id. They expose their identity through accessors
(``idx.spz_uid()``, ``idx.spz_name()``, ``idx.spz_provider()``) and the provider's own metadata as plain
attributes (``start_date``, ``description``, ...). Inventories are refreshed when Speasy is imported and
cached locally; ``inventories.cache_retention_days`` (see :doc:`configuration`) sets how long a cached
copy is considered fresh.

Product types
-------------

Most calls to :func:`speasy.get_data` return a :class:`~speasy.products.variable.SpeasyVariable`, a
single time series (see :doc:`plotting`, :doc:`numpy` and :doc:`scipy` for what you can do with one). A few other product
types exist for specific use cases:

- :class:`~speasy.products.catalog.Event` — a time interval (like a ``DateTimeRange``) with attached metadata.
- :class:`~speasy.products.catalog.Catalog` — an ordered collection of ``Event`` objects, e.g. all the
  intervals where a particular phenomenon was detected.
- :class:`~speasy.products.timetable.TimeTable` — an ordered collection of plain time intervals, commonly
  used to drive a batch fetch (pass a ``TimeTable`` as ``get_data()``'s time range to retrieve one
  variable for every interval at once).
- :class:`~speasy.products.dataset.Dataset` — a collection of ``SpeasyVariable`` objects for every
  parameter of an instrument/dataset, indexable by variable name (``dataset['b_gse']``).

Today, Catalogs, TimeTables, and Datasets are produced by the :doc:`AMDA module <amda/amda>`; see its
:ref:`amda_catalogs_timetables` and :ref:`amda_datasets` sections for a walkthrough, including
:ref:`using a TimeTable to batch-fetch and analyze data <amda_timetable_batch_fetch>`.

.. _time_ranges:

Time ranges
-----------

``get_data()`` and similar calls accept ``start``/``stop`` as plain strings (e.g. ``"2016-6-2"`` or
``"2018-01-01T01:00:00"``), :class:`~datetime.datetime` objects, :class:`numpy.datetime64` values of
any unit (``np.datetime64('2016-06-02')`` works), or float Unix-epoch times (seconds since 1970).
Naive datetimes and strings without timezone information are assumed to be **UTC**, while
timezone-aware datetimes and strings with an offset (e.g. ``"2018-01-01T01:00:00+02:00"``) are
converted to UTC. Any precision from whole days down to sub-second
(e.g. ``"2018-01-01T01:00:00.123456"``) is accepted.

.. _coordinate_systems:

Coordinate systems
------------------

Trajectories and vector quantities only mean something together with the coordinate frame they are
expressed in, and each provider offers its own set of frames. Some let you pick one per request
(SSCWeb's ``coordinate_system``, CDPP 3DView's ``coordinate_frame``), some make it a level of the
inventory tree (UiowaEphTool), and some bake it into the product itself (the CDAWeb and CSA products
named ``..._gse``, ``B_RTN``, and so on).

See each provider's page for the frames it supports and how to select one. Picking the wrong frame
returns believable-looking but physically wrong vectors, so it is worth checking which frame you
actually got before comparing data across missions.

Units
-----

Speasy does not convert units: values and the ``UNITS`` metadata field are passed through exactly as
provided by the source service (AMDA, CDAWeb, ...). Check a variable's ``.unit`` attribute or its
``UNITS``/``CATDESC`` metadata to know what you're actually looking at.

Errors and empty results
------------------------

A **known** product (one Speasy's inventory recognizes) with no data in the requested time range makes
``get_data()`` (and ``get_dataset()``/``get_catalog()``/``get_timetable()``) return ``None`` rather than
raise. Always check for ``None`` before using the result:

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

    >>> import speasy as spz
    >>> spz.get_data("amda/this_product_does_not_exist", "2018-01-01", "2018-01-02")
    Traceback (most recent call last):
        ...
    ValueError: Unknown product: this_product_does_not_exist

Network failures raise as well, so a robust caller wants a ``try``/``except`` around the call and a
``None`` check on the result.

.. note::
    **Boundary samples.** Ranges are half-open: ``[start, stop)`` — the sample at ``start`` is
    included, the one at ``stop`` is not, so adjacent requests tile without duplicating the
    boundary sample. If no sample falls inside the requested range (e.g. a very short request
    between two samples), the result is simply empty.

Fill values and data gaps
~~~~~~~~~~~~~~~~~~~~~~~~~

Providers mark missing samples with a **fill sentinel** (e.g. ``-1e31``) stored right inside
``.values``, together with a ``FILLVAL`` metadata entry. Plain NumPy statistics know nothing about
it, so ``np.mean(var)`` silently averages the sentinel in and returns nonsense. Replace fill values
by NaN first — :meth:`~speasy.products.variable.SpeasyVariable.replace_fillval_by_nan` returns a new
variable (pass ``inplace=True`` to modify it in place) — then use NaN-aware NumPy functions.
:meth:`~speasy.products.variable.SpeasyVariable.sanitized` goes further and returns a copy with the
fill/NaN/out-of-range rows dropped entirely, and ``.plot()`` already masks fill values by default:

    >>> import numpy as np
    >>> from speasy.products.variable import SpeasyVariable
    >>> from speasy.core.data_containers import VariableTimeAxis, DataContainer
    >>> # a small variable built locally so this example runs offline
    >>> time = np.arange("2018-01-01", "2018-01-05", dtype="datetime64[D]").astype("datetime64[ns]")
    >>> var = SpeasyVariable(axes=[VariableTimeAxis(values=time)],
    ...                      values=DataContainer(values=np.array([1., 2., -1e31, 4.]),
    ...                                           meta={"FILLVAL": -1e31}),
    ...                      columns=["Bz"])
    >>> np.mean(var) < 0  # the -1e31 sentinel poisons the statistics
    np.True_
    >>> clean = var.replace_fillval_by_nan()
    >>> np.nanmean(clean)  # NaN-aware mean of the three valid samples
    np.float64(2.3333333333333335)
