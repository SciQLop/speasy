Direct archive access
=====================

.. toctree::
   :maxdepth: 1

The Direct Archive Access module lets you load data from any local or remote archive of
`CDF <https://cdf.gsfc.nasa.gov/>`_ or `NetCDF <https://www.unidata.ucar.edu/software/netcdf/>`_
files directly into Speasy — no web service required. Other formats (HAPI, plain text, your lab's
own binary format...) are supported through a pluggable codec system — see
:ref:`supported_file_formats` below.

This is useful when:

- You have your own data files on disk or on a lab server
- A public archive (e.g. CDAWeb) hosts files you want to access directly rather than through an API
- You want to share a dataset configuration with colleagues

Once configured, the data appears in Speasy's inventory and can be loaded with ``spz.get_data()`` like any other product.

How it works
------------

Most space physics data archives follow a simple pattern: files are organized in folders by date
(e.g. one CDF file per day, stored in yearly or monthly directories). Speasy exploits this predictable
structure. You describe the URL pattern and file organization in a short YAML file, and Speasy handles the rest:
it figures out which files to download for a given time range, loads them, and merges the results into a
single ``SpeasyVariable``.

.. note::
    The data files must follow the `ISTP <https://spdf.gsfc.nasa.gov/istp_guide/>`_ (International
    Solar-Terrestrial Physics) CDF/NetCDF conventions — a standard set of metadata attributes
    (``DEPEND_0``, ``UNITS``, ``FILLVAL``, ...) that most public space physics archives, including
    CDAWeb, already use. For non-ISTP files or other formats, see :ref:`writing_a_codec` below.


.. _supported_file_formats:

Supported file formats
-----------------------

.. list-table::
   :widths: 20 20 60
   :header-rows: 1

   * - Format
     - ``codec:`` value
     - Notes
   * - CDF (ISTP)
     - ``cdf`` (or ``application/x-cdf``)
     - Built in, no extra dependency. Default when ``codec`` is omitted.
   * - NetCDF (ISTP)
     - ``nc`` or ``nc4`` (or ``application/x-netcdf``, ``application/netcdf``)
     - Requires the optional `netCDF4 <https://pypi.org/project/netCDF4/>`_ package. Without it,
       any dataset declaring ``codec: nc`` is silently skipped with a warning at import time.
   * - HAPI CSV
     - ``hapi/csv`` (exact name, no extension/mimetype alias)
     - Works with inline ``variables:`` datasets only — see the caveat in
       :ref:`yaml_field_reference` below.
   * - HAPI Binary
     - ``hapi/binary`` (exact name, no extension/mimetype alias)
     - Same limitation as HAPI CSV.
   * - Anything else
     - a name you choose
     - Write your own codec — see :ref:`writing_a_codec`.

A codec can also be referenced by its Python class name (e.g. ``codec: IstpCdf``,
``codec: IstpNetCDF``) — every spelling that resolves to the same codec is interchangeable.
Resolution is a flat, case-sensitive lookup, so pick a distinctive ``codec:`` value if you write
your own.

Quick start: adding a dataset
------------------------------

**Step 1: Find the inventory directory**

Create a YAML file (e.g. ``my_datasets.yaml``) in Speasy's user inventory directory.
On Linux this is ``~/.config/speasy/archive/``, on macOS ``~/Library/Application Support/speasy/archive/``
(the ``LPP`` author segment only appears in the Windows path, ``%LOCALAPPDATA%\LPP\speasy\archive``).
You can confirm the exact path:

    >>> import speasy as spz
    >>> print(spz.data_providers.generic_archive.user_inventory_dir()) # doctest: +SKIP

**Step 2: Describe your dataset in YAML**

Here is a minimal example for THEMIS-A FGM data hosted at CDPP, with one CDF file per day:

.. code-block:: YAML

    tha_fgm:
      inventory_path: my_data/THEMIS/THA
      master_cdf: http://cdpp.irap.omp.eu/themisdata/tha/l2/fgm/0000/tha_l2_fgm_00000000_v01.cdf
      split_frequency: daily
      split_rule: regular
      url_pattern: http://cdpp.irap.omp.eu/themisdata/tha/l2/fgm/{Y}/tha_l2_fgm_{Y}{M:02d}{D:02d}_v\d+.cdf
      use_file_list: true

Alternatively, you can describe the variables inline — no master file needed, and no network access at
inventory build time. Speasy then needs the metadata a master file would have provided, so each variable
carries its own ``meta`` block, alongside a dataset-level one:

.. code-block:: YAML

    my_dataset:
      inventory_path: my_data/MISSION/INSTRUMENT
      meta:
        Mission_group: MISSION
        Data_type: l2
      variables:
        Bx:
          meta:
            UNITS: nT
            CATDESC: B along X
        By:
          meta:
            UNITS: nT
            CATDESC: B along Y
      codec: nc
      split_rule: regular
      url_pattern: https://my_server.net/data/{Y}/{M:02d}/data_{Y}{M:02d}{D:02d}.nc

.. warning::
    A bare list of names (``variables: [Bx, By]``) is **not** supported: the dataset is skipped and a
    warning is emitted in the log. Both the dataset-level ``meta`` and a ``meta`` for every variable
    are required.

.. note::
    ``codec`` here has nothing to do with discovering variables (they're already given) — it only
    tells Speasy how to decode the actual data files at fetch time. It defaults to ``cdf`` if omitted,
    so set it explicitly whenever ``url_pattern`` doesn't point to CDF files, as above. An unrecognized
    codec skips the whole dataset with a warning at import time, rather than failing inside every
    subsequent ``get_data()`` call.

.. important::
    ``get_data()`` builds its result from the actual data file's own attributes, but ``meta``
    above is also patched onto every ``get_data()`` result by default — not just when *browsing*
    the inventory (``spz.inventories.data_tree...``). By default (``meta_priority: file``) it only
    fills in fields the file doesn't already have; set ``meta_priority: yaml`` if you want a field
    declared here to override the file's own value instead:

    .. code-block:: YAML

        meta_priority: file  # default: YAML meta only fills fields the file doesn't have
        meta_priority: yaml  # YAML meta overrides the file's own value on a clash

Or, if the data files are in a format other than CDF (e.g. NetCDF), point to a master file and specify the codec:

.. code-block:: YAML

    my_nc_dataset:
      inventory_path: my_data/MISSION/INSTRUMENT
      master_file: https://my_server.net/masters/dataset_master.nc
      codec: nc
      split_rule: regular
      url_pattern: https://my_server.net/data/{Y}/{M:02d}/data_{Y}{M:02d}{D:02d}.nc

.. note::
    ``master_cdf`` is the legacy key for CDF master files.
    It is deprecated but remains supported.
    Prefer ``master_file`` + ``codec`` for new entries.

A master file's own metadata can be patched too — add a ``meta`` block alongside ``master_file``
just like the inline format, controlled by the same ``meta_priority``:

.. code-block:: YAML

    my_nc_dataset:
      inventory_path: my_data/MISSION/INSTRUMENT
      master_file: https://my_server.net/masters/dataset_master.nc
      codec: nc
      meta:
        Mission_group: MISSION       # the master doesn't have this: always added
        Data_type: corrected-l2      # the master does have this: only wins with meta_priority: yaml
      meta_priority: yaml
      split_rule: regular
      url_pattern: https://my_server.net/data/{Y}/{M:02d}/data_{Y}{M:02d}{D:02d}.nc

**Step 3: Restart Python and use it**

After saving the YAML file, restart your Python session (the inventory is built at import time):

    >>> import speasy as spz # doctest: +SKIP
    >>> # Your dataset now appears in the inventory
    >>> spz.inventories.data_tree.archive.my_data.THEMIS.THA.tha_fgm # doctest: +SKIP
    >>> # Get data as usual
    >>> tha_b = spz.get_data("archive/my_data/THEMIS/THA/tha_fgm/tha_fgl_btotal", "2018-06-01", "2018-06-02") # doctest: +SKIP

.. tip::
    The individual variables within each dataset (like ``tha_fgl_btotal``) are discovered automatically
    from the master CDF file. Use tab-completion in IPython/Jupyter to explore them.

.. tip::
    Speasy caches the *result* of reading a master file for 7 days, not just the raw download — if you
    only change the master file itself (not the YAML), restarting Python alone may not pick up the
    change for up to a week. See :ref:`archive_troubleshooting` below.


.. _yaml_field_reference:

YAML field reference
--------------------

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Field
     - Description
   * - **dataset_name** (top-level key)
     - A name for your dataset. This becomes the last part of the inventory path.
   * - **inventory_path**
     - Where the dataset appears in ``spz.inventories.data_tree.archive``. Slashes create a nested hierarchy
       (e.g. ``my_data/THEMIS/THA`` → ``archive.my_data.THEMIS.THA``).
   * - **meta**
     - Dataset-level metadata (e.g. ``Mission_group``, ``Data_type``). Required together with
       **variables**; optional alongside **master_file**/**master_cdf**, where it patches onto the
       metadata extracted from the master (see **meta_priority** for which side wins a clash).
       Patched onto both the inventory browser entries and every ``get_data()`` result by default;
       **meta_priority** only controls which side wins on a clash, not whether patching happens.
       Note that browsing the inventory only ever shows a curated subset of a master file's own
       attributes (things like ``CATDESC``, ``UNITS``, ``FILLVAL``) — anything else you want visible
       while browsing (e.g. ``Mission_group``) must come from this **meta** block, not the master file.
   * - **meta_priority**
     - ``file`` (default) or ``yaml``. The single knob resolving every YAML-vs-file metadata clash
       in this dataset: **meta** vs. the master's own metadata at inventory-build time, and the
       built inventory metadata vs. the real data file's own attributes inside every ``get_data()``
       call. Either way, fields declared only in YAML always come through. Has no effect for inline
       **variables** datasets (there's no master to clash with) — it still applies to the
       ``get_data()``-time patching in that case.
   * - **variables**
     - Inline description of the dataset's variables, as a mapping of variable name to a ``meta`` block.
       Use this when you want to avoid any network access at inventory build time. Both a dataset-level
       **meta** and a ``meta`` for each variable are required — a bare list of names is skipped.
   * - **master_file**
     - URL or local path to a master file in any supported format. Speasy opens it once with the
       specified codec to discover the variable names. Replaces ``master_cdf`` for non-CDF formats.
       If both **master_file**/**master_cdf** and **variables** are present, **variables** silently
       wins and the master is ignored entirely.
   * - **codec**
     - Codec identifier used both to discover variables from ``master_file`` and, for any dataset
       (``master_file`` or ``variables``), to decode the actual data files at fetch time. Accepts a
       file extension (``cdf``, ``nc``), a MIME type (``application/x-cdf``), a codec name
       (``hapi/csv``) or a class name. Optional, defaults to ``cdf``; an unrecognized value skips the
       whole dataset with a warning at import time. A codec that can't enumerate a master file's
       variables (like the built-in HAPI codecs) also skips the dataset the same way — use
       **variables** with those instead.
   * - **master_cdf** *(deprecated)*
     - URL or local path to a CDF master file. Speasy reads it once to discover which variables the
       dataset contains. Prefer ``master_file`` + ``codec: cdf`` for new entries.
   * - **split_rule**
     - How the files are organized: ``regular`` (predictable, one file per time period) or ``random``
       (variable-length files like burst data). See :ref:`random_split_datasets`. **Required, no
       default** — see :ref:`archive_troubleshooting` for what happens if it's missing.
   * - **split_frequency**
     - Time granularity of the files: ``daily`` (default), ``monthly``, ``yearly``, or ``none``.
       For ``regular`` datasets, this is how often a new file starts (``none`` treats the whole
       dataset as one fixed file — see :ref:`static_datasets`).
       For ``random`` datasets, this is how often a new *folder* starts (Speasy scans each folder for matching files).
   * - **url_pattern**
     - The URL template for data files. Date placeholders are expanded for each time period.
       Can include Python regular expressions for unpredictable parts (e.g. file version numbers)
       when ``use_file_list`` is ``true``. See the :ref:`url_placeholders` table below. Always use
       forward slashes for directory separators, even for a local Windows path — see
       :ref:`archive_platform_notes`.
   * - **use_file_list**
     - If ``true``, Speasy lists the files in each directory and selects the last one matching
       the URL pattern. Set this to ``true`` when parts of the filename are unpredictable (like version numbers).
       Default: ``false``.
   * - **fname_regex**
     - Only for ``random`` split datasets. A Python regular expression to extract the start date
       (and optionally stop date and version) from each filename. See :ref:`random_split_datasets`.

.. _url_placeholders:

URL pattern placeholders
^^^^^^^^^^^^^^^^^^^^^^^^

The ``url_pattern`` uses Python ``str.format()`` syntax. Available placeholders:

.. list-table::
   :widths: 15 25 30
   :header-rows: 1

   * - Placeholder
     - Meaning
     - Example output
   * - ``{Y}``
     - 4-digit year
     - ``2018``
   * - ``{y}``
     - 2-digit year
     - ``18``
   * - ``{M}``
     - Month (no padding)
     - ``1`` .. ``12``
   * - ``{M:02d}``
     - Month (zero-padded)
     - ``01`` .. ``12``
   * - ``{D}``
     - Day (no padding)
     - ``1`` .. ``31``
   * - ``{D:02d}``
     - Day (zero-padded)
     - ``01`` .. ``31``
   * - ``{j}``
     - Day of year
     - ``1`` .. ``366``
   * - ``{H}``
     - Hour (24h)
     - ``0`` .. ``23``
   * - ``{I}``
     - Hour (12h)
     - ``0`` .. ``11``
   * - ``{p}``
     - AM/PM, paired with ``{I}``
     - ``AM`` or ``PM``

Regex parts of the pattern (like ``\d+`` for version numbers) are only interpreted when ``use_file_list: true``.

.. _random_split_datasets:

Randomly split datasets (burst data)
-------------------------------------

Some datasets don't produce one file per day. Instead, files cover irregular time intervals
(e.g. burst-mode data that only records during events). For these, use ``split_rule: random``.

The key difference is the ``fname_regex`` field: a regular expression that Speasy applies to each filename
to extract the time range it covers.

.. code-block:: YAML

    mms1_fpi_brst_l2_des_moms:
      inventory_path: cda/MMS/MMS1/FPI/BURST/MOMS
      master_cdf: "https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/mms1_fpi_brst_l2_des-moms_00000000_v01.cdf"
      split_rule: random
      split_frequency: monthly
      url_pattern: 'https://cdaweb.gsfc.nasa.gov/pub/data/mms/mms1/fpi/brst/l2/des-moms/{Y}/{M:02d}/mms1_fpi_brst_l2_des-moms_{Y}{M:02d}\d+_v\d+.\d+.\d+.cdf'
      use_file_list: true
      fname_regex: 'mms1_fpi_brst_l2_des-moms_(?P<start>\d+)_v(?P<version>[\d\.]+)\.cdf'

**How it works:** for each month in the requested time range, Speasy lists all files in the folder,
applies ``fname_regex`` to extract the start time from each filename, keeps only the files that overlap
with the requested interval, and loads them. If the file list looks stale (a fetch attempt gets an
HTTP 404), Speasy automatically retries once with a fresh listing, in case a new file version appeared
since the last time the folder was scanned.

**fname_regex named groups:**

- ``(?P<start>...)`` — start date extracted from the filename (mandatory). Must be parsable as a date.
- ``(?P<stop>...)`` — stop date (optional). If absent, Speasy assumes each file ends when the next one starts.
- ``(?P<version>...)`` — file version (optional). Captured for readability but not currently used
  to select between multiple versions of the same time range — if several matching files overlap,
  Speasy loads all of them.


.. _static_datasets:

Fixed-URL datasets (no date placeholders)
-------------------------------------------

If ``url_pattern`` has no ``{Y}``/``{M}``/``{D}`` placeholders at all — a single file that covers your
whole dataset, rather than one file per period — set ``split_frequency: none``. Without it, Speasy
would still re-resolve (and re-fetch, subject to caching) the same unchanging URL once per default
("daily") period covered by a query, which is wasted work for a file that never changes:

.. code-block:: YAML

    my_static_dataset:
      inventory_path: my_data/MISSION/INSTRUMENT
      meta:
        Mission_group: MISSION
      variables:
        Bx:
          meta:
            UNITS: nT
      split_rule: regular
      split_frequency: none
      url_pattern: https://my_server.net/data/full_mission.cdf


.. _archive_metadata_and_caching:

Metadata visibility & caching
-------------------------------

A few things about metadata and caching are easy to miss:

- **Inventory browsing shows a curated subset of a master file's attributes** (things like
  ``CATDESC``, ``FIELDNAM``, ``UNITS``, ``FILLVAL``, ``LABLAXIS``), not everything the file
  contains. ``get_data()`` results, by contrast, carry the file's **complete, unfiltered** attribute
  set, read live from the fetched file. So a dataset-level attribute like ``Mission_group`` used in
  the examples above never comes from the master file's own metadata — it only appears if you add it
  yourself via ``meta:``.
- **Master file extraction is cached for 7 days**, on disk, across process restarts — not just the raw
  download, but the parsed result (variable names, metadata). If you only change the master file
  itself (not the YAML entry), a Python restart alone won't pick up the change until the cache expires.
  See the :ref:`user/configuration:Cache section` to locate and clear Speasy's disk cache if you
  need a fresher read sooner.
- **Reachability of a remote master is only host-level**, not a check that the exact URL actually
  exists: Speasy checks that the server responds (cached for 2 minutes), then tries to fetch the
  master. A live host serving a 404 for that specific path fails the same way as a genuinely
  unreachable host — the dataset is silently skipped with a warning, not an error.
- **A local master file's path is never checked for existence at inventory build time either** — a
  typo'd local path is only caught when Speasy actually tries to open it, and produces the same
  silent "could not be loaded" warning as any other malformed entry.

``get_data()`` on an archive product also accepts a few extra keyword arguments:

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Keyword
     - Supported?
   * - ``force_refresh=True``
     - Yes — bypasses the file-listing cache, useful right after a remote file changed.
   * - ``disable_cache=True`` / ``prefer_cache=True``
     - Yes — the usual cache-control kwargs, same as other providers.
   * - ``extra_http_headers=...`` / ``progress=...``
     - **No** — currently raises a ``TypeError`` if passed. These work for AMDA/CDA but aren't wired
       through for archive datasets yet.


.. _archive_troubleshooting:

Troubleshooting
------------------

- **A dataset builds fine but** ``get_data()`` **raises** ``TypeError: get_product() missing 1
  required positional argument: 'split_rule'``: your YAML entry is missing ``split_rule`` (or,
  similarly, ``url_pattern``). Unlike most malformed-entry mistakes, these two aren't validated
  until the first actual fetch, so the dataset can look completely normal in the inventory right up
  until you call ``get_data()``.
- **A dataset silently doesn't appear in the inventory at all**: check the log for a warning — the
  usual causes are an unreachable/nonexistent master file, an unrecognized ``codec``, or a codec that
  can't enumerate a master file's variables (see :ref:`supported_file_formats`).
- ``get_data()`` **returns** ``None`` **rather than raising**: this is normal when the requested time
  range isn't covered by any file, or falls entirely outside the dataset's actual data range — it's
  not an error.
- **Nothing changed after I updated my master file**: see the 7-day caching note in
  :ref:`archive_metadata_and_caching` above.


Extra inventory directories
----------------------------

Beyond the default user directory, you can tell Speasy to scan additional directories for YAML files:

.. code-block:: ini

    [ARCHIVE]
    extra_inventory_lookup_dirs = /shared/lab/speasy_inventories,/another/path

Or via the environment variable ``SPEASY_ARCHIVE_EXTRA_INVENTORY_LOOKUP_DIRS``.


.. _archive_platform_notes:

Platform notes (Windows, macOS, Linux)
-----------------------------------------

The archive module has no platform-specific *behavior* beyond the following two points — everything
else (YAML syntax, codecs, caching) works identically on every OS Speasy supports.

- **Always use forward slashes (``/``) for directory separators in** ``url_pattern``, even for a
  local Windows path (``C:/data/{Y}/file_{Y}{M:02d}{D:02d}.cdf`` rather than backslashes). This isn't
  just a style preference: whenever ``use_file_list: true`` or ``split_rule: random``, Speasy splits
  the pattern into a folder and a filename regex on the last ``/`` — a pattern with no forward slash
  at all fails outright. Regex bits like ``\d+`` inside the trailing filename segment are unaffected,
  since they don't contain ``/``.
- **Don't prefix a local Windows path with** ``file://``. A bare path like ``C:/data/master.cdf`` (or
  ``C:\data\master.cdf``) already works correctly as ``master_file``/``url_pattern`` — adding
  ``file://`` in front only matters (and is only reliably handled) for genuine ``file://`` URLs, and
  can misbehave with a drive letter when combined with ``use_file_list: true``.

Default directories (set by the `appdirs <https://pypi.org/project/appdirs/>`_ library speasy uses
internally) differ by OS, and — on Linux only — the inventory directory and the codecs directory
(see :ref:`writing_a_codec`) live under different bases:

.. list-table::
   :widths: 20 40 40
   :header-rows: 1

   * - OS
     - Default inventory directory
     - Default codecs directory
   * - Linux
     - ``~/.config/speasy/archive/``
     - ``~/.local/share/speasy/codecs/``
   * - macOS
     - ``~/Library/Application Support/speasy/archive/``
     - ``~/Library/Application Support/speasy/codecs/``
   * - Windows
     - ``%LOCALAPPDATA%\LPP\speasy\archive\``
     - ``%LOCALAPPDATA%\LPP\speasy\codecs\``


.. _writing_a_codec:

Adding support for a new file format
--------------------------------------

There are two ways to teach Speasy a new file format, depending on what you need:

- :ref:`writing_a_reusable_codec` — the recommended approach for anything you'll reuse: it
  integrates with the YAML inventory system (``codec: your_codec_name``), so your dataset gets
  discovered from a ``master_file`` (if your codec supports it), gets normal inventory/tab-completion
  support, and works exactly like a built-in format for anyone with your codec file installed.
- :ref:`ad_hoc_custom_reader` — a quicker escape hatch for a one-off script: call
  ``get_product()`` directly with your own reading function. Nothing is registered, so it can't be
  referenced from a YAML ``codec:`` entry, appear in tab-completion, or be discovered from a master file.

.. _writing_a_reusable_codec:

Writing a reusable codec (recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A codec is a small class implementing ``speasy.core.codecs.codec_interface.CodecInterface``:

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Method / property
     - Required?
   * - ``load_variables(variables, file, cache_remote_files=True, **kwargs)``
     - Yes. Returns a ``{name: SpeasyVariable}`` mapping for the requested variable names.
   * - ``load_variable(variable, file, cache_remote_files=True, **kwargs)``
     - Yes. Same as above for a single variable (often just delegates to ``load_variables``).
   * - ``save_variables(variables, file=None, **kwargs)``
     - Yes, but may simply ``raise NotImplementedError`` — a read-only codec is fine.
   * - ``list_variables(file)``
     - Only if you want ``master_file:`` discovery to work for this codec (see below). Otherwise
       leave it out — the default implementation raises ``NotImplementedError``, and the dataset
       falls back to needing inline ``variables:`` instead.
   * - ``supported_extensions`` / ``supported_mimetypes`` (properties)
     - Yes, may return an empty list if you'd rather only be selected by ``name``.
   * - ``name`` (property)
     - Yes. Must be globally unique — pick something distinctive and namespaced (e.g.
       ``"my_lab/my_format"``), not a generic word.

Decorate the class with ``@register_codec`` and drop the file in Speasy's user codecs directory (see
the table in :ref:`archive_platform_notes` above), or any directory listed in the ``user_codecs_extra_dirs``
config entry / ``SPEASY_CORE_USER_CODECS_EXTRA_DIRS`` environment variable — every ``.py`` file there
is loaded automatically the next time Speasy starts.

.. warning::
    Codec files are **executed directly**, not imported as a regular module — keep this in mind before
    placing a file you didn't write yourself in a codecs directory. Three consequences worth knowing
    before you write one:

    1. **A broken codec file breaks** ``import speasy`` **for everyone**, not just archive datasets — a
       syntax error, or a ``name``/extension/mimetype collision with another registered codec, crashes
       at import time with an uncaught exception. Unlike a malformed YAML entry (which only costs that
       one dataset), there's no per-codec error containment.
    2. **Import codec/registry helpers from their submodules**, not the ``speasy.core.codecs`` package
       itself: ``from speasy.core.codecs.codec_interface import CodecInterface`` and
       ``from speasy.core.codecs.codecs_registry import register_codec``. Codec files load while that
       package is still mid-import, so importing from the package directly raises a circular
       ``ImportError``.
    3. **Put every import a method needs inside that method**, not at the top of the codec file — a
       top-level ``import numpy as np`` will raise ``NameError: name 'np' is not defined`` the first
       time a method tries to use it, because of how the file is executed. This doesn't affect the
       ``class ...:`` and ``@register_codec`` lines themselves, only names used inside ``def`` bodies.

Minimal working example — a codec for a simple ``timestamp,var1,var2,...`` CSV file, supporting both
inline ``variables:`` and ``master_file:`` discovery:

.. code-block:: python

    # ~/.local/share/speasy/codecs/my_csv_codec.py (or a dir listed in user_codecs_extra_dirs)

    from speasy.core.codecs.codec_interface import CodecInterface
    from speasy.core.codecs.codecs_registry import register_codec


    @register_codec
    class MyCsvCodec(CodecInterface):

        def _read(self, file):
            import csv
            with open(file, newline='') as f:
                rows = list(csv.reader(f))
            header, data = rows[0], rows[1:]
            return header, data

        def list_variables(self, file):
            header, _ = self._read(file)
            return header[1:]  # everything but the timestamp column

        def load_variables(self, variables, file, cache_remote_files=True, **kwargs):
            import numpy as np
            from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer

            header, data = self._read(file)
            columns = {name: i for i, name in enumerate(header)}
            time = np.array([row[0] for row in data], dtype='datetime64[ns]')
            return {
                name: SpeasyVariable(
                    axes=[VariableTimeAxis(values=time)],
                    values=DataContainer(values=np.array([float(row[columns[name]]) for row in data])),
                )
                for name in variables
            }

        def load_variable(self, variable, file, cache_remote_files=True, **kwargs):
            return self.load_variables([variable], file, cache_remote_files, **kwargs).get(variable)

        def save_variables(self, variables, file=None, **kwargs):
            raise NotImplementedError("read-only demo codec")

        @property
        def supported_extensions(self):
            return ["mycsv"]

        @property
        def supported_mimetypes(self):
            return []

        @property
        def name(self):
            return "my_csv_codec"

Used from a YAML inventory entry as ``codec: mycsv`` (or ``codec: my_csv_codec``), either with a
``master_file:`` (thanks to ``list_variables``) or an inline ``variables:`` block, exactly like a
built-in format.

.. _ad_hoc_custom_reader:

One-off custom reader (quick, not YAML-integrated)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For a quick script or prototype, you can skip writing a codec entirely and call
``speasy.core.direct_archive_downloader.get_product`` directly with your own reader function.
This bypasses the YAML inventory and codec registry completely — nothing is discoverable or reusable
from a ``codec:`` entry, it's just a plain function call.

Your reader function receives a file URL and a variable name, and returns a ``SpeasyVariable`` (or ``None``):

.. code-block:: python

    from speasy.products import SpeasyVariable

    def my_reader(url: str, variable: str, **kwargs) -> SpeasyVariable or None:
        # Load data from url, build and return a SpeasyVariable
        ...

Then call ``get_product`` with your reader:

.. code-block:: python

    from speasy.core.direct_archive_downloader import get_product

    data = get_product(
        url_pattern="https://example.com/data/{Y}/{M:02d}/mydata_{Y}{M:02d}{D:02d}_v\d+.cdf",
        start_time="2023-06-19",
        stop_time="2023-06-20",
        variable="B",
        split_rule="regular",
        split_frequency="daily",
        use_file_list=True,
        file_reader=my_reader,
    )

Example: reading non-ISTP Solar Orbiter LFR snapshots
""""""""""""""""""""""""""""""""""""""""""""""""""""""

This example shows a custom reader for Solar Orbiter RPW/LFR waveform snapshots.
These files contain multiple snapshots at different sampling rates packed into a single CDF,
so the standard reader cannot handle them.

.. code-block:: python

    import speasy as spz
    from speasy.products import SpeasyVariable, VariableTimeAxis, DataContainer
    from speasy.core.direct_archive_downloader import get_product
    from speasy.core.any_files import any_loc_open
    import numpy as np
    import pycdfpp
    import matplotlib.pyplot as plt

    def snapshots_B_custom_reader(url, variable='B', sampling = 24576.):
        cdf=pycdfpp.load(any_loc_open(url,cache_remote_files=True).read())
        # all snapshots for different sampling rates are stored in the same variable
        # so we need to build an index of the snapshots with the desired sampling rate
        indexes = cdf["SAMPLING_RATE"].values[:] == sampling
        # build time axis from each snapshot start time and sampling rate
        star_times = pycdfpp.to_datetime64(cdf["Epoch"].values[indexes]).astype(np.int64)
        time = np.linspace(star_times, star_times+2048*int(1e9/sampling),num=2048).astype('datetime64[ns]').T.reshape(-1)
        sel_values = cdf[variable].values[indexes]
        values = np.empty((sel_values.shape[0]*sel_values.shape[2],3), sel_values.dtype)
        values[:,0] = sel_values[:,0,:].reshape(-1)
        values[:,1] = sel_values[:,1,:].reshape(-1)
        values[:,2] = sel_values[:,2,:].reshape(-1)
        if 'RTN' in variable:
            labels = ['Bxrtn', 'Byrtn', 'Bzrtn']
        else:
            labels = ['Bx', 'By', 'Bz']
        return SpeasyVariable(axes=[VariableTimeAxis(values= time)],values=DataContainer(values), columns=labels)


    lfr_b_F2 = get_product(url_pattern="http://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/data/solar-orbiter/rpw/science/l2/lfr-surv-swf-b/{Y}/solo_l2_rpw-lfr-surv-swf-b_{Y}{M:02}{D:02}_v\d+.cdf",
                        start_time="2023-06-19T02:01:59",
                        stop_time="2023-06-19T02:02:08",
                        variable="B",
                        split_rule="regular",
                        split_frequency="daily",
                        use_file_list=True,
                        file_reader=snapshots_B_custom_reader,
                        sampling = 256.
                        )
    plt.figure()
    lfr_b_F2.plot()
    plt.show()

This produces the following plot:

.. image:: LFR_Snapshot.png
    :width: 800
    :align: center
