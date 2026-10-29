Coordinated Data Analysis Web (CDAWeb)
======================================

.. toctree::
   :maxdepth: 1

The `Coordinated Data Analysis Web (CDAWeb) <https://cdaweb.gsfc.nasa.gov/>`__ contains selected public non-solar heliophysics
data from current and past heliophysics missions and projects. Many datasets from current missions are updated regularly
(even daily), including reprocessing older time periods, and SPDF only preserves the latest version.

Basics: Getting data from CDA module
------------------------------------

The easiest solution is to use your python terminal completion and browse ``spz.inventories.tree.cda`` to find
your product.
Once you have found your product, then simply ask CDA module to get data for the provided time range:

    >>> import speasy as spz
    >>> # Let's assume you wanted to get Solar Orbiter 'Magnetic field vector in RTN coordinates'
    >>> solo_mag_rtn = spz.get_data(spz.inventories.tree.cda.Solar_Orbiter.SOLO.MAG.SOLO_L2_MAG_RTN_NORMAL_1_MINUTE.B_RTN, "2021-01-01", "2021-01-02")
    >>> solo_mag_rtn.columns
    ['B_r', 'B_t', 'B_n']
    >>> solo_mag_rtn.values.shape
    (1438, 3)

A product can also be named by its ``"DATASET/VARIABLE"`` string id, and ``get_variable()``
takes the dataset and variable as separate arguments:

.. code-block:: python

    import speasy as spz
    b = spz.get_data("cda/AC_H0_MFI/BGSEc", "2018-01-01", "2018-01-02")
    b = spz.cda.get_variable(dataset="AC_H0_MFI", variable="BGSEc",
                             start_time="2018-01-01", stop_time="2018-01-02")

Each dataset only covers a finite time range; ``parameter_range()`` and ``dataset_range()``
tell you what it is before you ask:

.. code-block:: python

    spz.cda.dataset_range("AC_H0_MFI")
    spz.cda.parameter_range("AC_H0_MFI/BGSEc")

Specific CDAWeb options
-----------------------

The CDAWeb module lets you choose the access method among ``BEST``, ``FILE``, and ``API``. The default is ``BEST``.

* ``BEST`` — automatically selects between ``FILE`` and ``API`` for each dataset.
* ``FILE`` — downloads data files directly from the CDAWeb archive. In this mode, a CDF
  dataset's metadata (variable names, units, labels) comes from the dataset's *master CDF*
  published by CDAWeb.
* ``API`` — retrieves data through the CDAWeb REST API.

.. warning::
    An unrecognized ``method=`` value silently falls back to the web service (``API``)
    instead of raising an error — a typo like ``method='FIL'`` therefore goes unnoticed.
    Double-check the spelling if a request doesn't behave as expected.

.. note::
    Most CDAWeb datasets are CDF, but about 70 are NetCDF. Those can go through ``FILE`` too, on two
    conditions the container format does not tell: their files must carry the ISTP attributes the
    NetCDF codec needs (``DEPEND_0``, ``VAR_TYPE``), and CDAWeb's file naming must really describe
    the archive. Speasy settles it by loading the requested variable from the first file it would
    download, and remembers the answer for a week. Whatever fails — plain NetCDF, the datasets
    CDAWeb describes with one sample file name instead of a pattern, the handful published as GIF or
    MPEG, and every parameter CDAWeb computes itself — keeps going through the REST API. None of
    the current NetCDF datasets passes, so this mostly opens the door for the ones to come.

.. note::
    ``FILE`` (and therefore ``BEST``, the default) reuses the :doc:`../direct_archive/direct_archive`
    machinery: Speasy translates CDAWeb's own description of how a dataset's files are named and
    foldered into the same ``split_rule`` / ``url_pattern`` / ``fname_regex`` settings you would
    write by hand for your own archive. Nothing to configure, but that page is where the behaviour
    is documented — in particular how file versions are picked when an archive publishes several
    for the same time range.

You can specify the method by passing the ``method`` argument to ``spz.get_data()``.

    >>> import speasy as spz
    >>> # Let's assume you wanted to get Solar Orbiter 'Magnetic field vector in RTN coordinates'
    >>> solo_mag_rtn = spz.get_data(spz.inventories.tree.cda.Solar_Orbiter.SOLO.MAG.SOLO_L2_MAG_RTN_NORMAL_1_MINUTE.B_RTN, "2021-01-01", "2021-01-02", method='API')
    >>> solo_mag_rtn.columns
    ['B_r', 'B_t', 'B_n']
    >>> solo_mag_rtn.values.shape
    (1438, 3)

You can also set the default method globally:

    >>> import speasy as spz
    >>> spz.config.cdaweb.preferred_access_method.set('BEST')

Waveform datasets
-----------------

Some CDAWeb files store waveforms as buckets: one record holds a snapshot of thousands of samples under a single
timestamp. Speasy reads these files itself, so that the product is a flat time series with **one timestamp per
sample**. This applies to the ``FILE`` method (and so to ``BEST``) only; the products keep their names.

The patched families are:

- Parker Solar Probe FIELDS: the ``DFB_DBM`` burst products (``VAC``, ``VDC``, ``DVAC``, ``DVDC``, ``SCM``) and
  ``TDS_WF``. Their patched products end with ``_f``, e.g. ``psp_fld_l2_dfb_dbm_vac1_f``.
- Solar Orbiter RPW: the TDS snapshots ``SOLO_L2_RPW-TDS-SURV-RSWF-B/E`` and ``-TSWF-B/E``, and the LFR snapshots
  ``SOLO_L2_RPW-LFR-SURV-SWF-B/E``.
- Van Allen Probes A and B, EMFISIS: the waveform receiver (WFR, including the continuous burst) and the high
  frequency receiver (HFR) waveforms.
- TRACERS TS1 and TS2: the search coil magnetometer (MSC) burst waveforms.
- Voyager 1 and 2: the plasma wave system (PWS) waveforms.

The SolO RPW LFR files mix three sampling rates, so each variable is split into one product per rate:
``<variable>_F0`` (24576 Hz), ``<variable>_F1`` (4096 Hz) and ``<variable>_F2`` (256 Hz), for example
``VDC_F2``. The unsplit variable is not exposed.

When the tail of a bucket overlaps the start of the next one, the overlapping samples are cut like speasy's
``merge`` does between files: the later bucket wins.

The SolO RPW waveform datasets are missing from CDAWeb's own inventory, so Speasy adds them, and they now appear
in ``spz.inventories.tree.cda``. They can only be read from files: if the archive can't be reached, ``get_data()``
raises an error instead of falling back to the web service.

    >>> import speasy as spz
    >>> rswf_e = spz.get_data('cda/SOLO_L2_RPW-TDS-SURV-RSWF-E/WAVEFORM_DATA', '2021-01-01', '2021-01-02')  # doctest: +SKIP
    >>> rswf_e.values.shape  # doctest: +SKIP
    (1167360, 3)
