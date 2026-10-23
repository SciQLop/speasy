Command line
============

Speasy installs a ``speasy`` command. With `uv <https://docs.astral.sh/uv/>`_ you can run it without
installing anything first:

.. code-block:: bash

    uvx speasy --help

Every command has its own ``--help``, e.g. ``speasy config add --help``.

Configuration
-------------

.. code-block:: bash

    speasy config show                    # every entry, its value, and where the value comes from
    speasy config show archive            # one section only
    speasy config set proxy.enabled false
    speasy config reset proxy.enabled     # back to the default value

The *Source* column says where each value comes from: ``env`` (an environment variable),
``file`` (the config file) or ``default``. An environment variable always wins over the config file,
and the commands that change an entry tell you when one is set.

Entries holding a list, such as directories, get ``add`` and ``remove``. Directories are stored as
absolute paths, so a relative path means the same folder wherever Speasy runs from:

.. code-block:: bash

    speasy config add archive.extra_inventory_lookup_dirs ~/lab/inventories
    speasy config remove archive.extra_inventory_lookup_dirs ~/lab/inventories

Providers
---------

.. code-block:: bash

    speasy providers list
    speasy providers disable csa cdpp3dview
    speasy providers enable csa           # any of a provider's names works

Archive inventories
-------------------

.. code-block:: bash

    speasy archive dirs                   # where Speasy looks for YAML files, and what it finds there
    speasy archive validate my_datasets.yaml --start 2018-06-01 --stop 2018-06-02

``validate`` exits with ``1`` when a file has a problem, see
:doc:`direct_archive/direct_archive` for what it checks.

Data and cache
--------------

.. code-block:: bash

    speasy get amda/imf 2018-06-01 2018-06-02                 # print a summary
    speasy get amda/imf 2018-06-01 2018-06-02 --output imf.cdf # or .csv, or .nc with netCDF4 installed
    speasy cache info

``cache warm`` downloads products ahead of time, e.g. before a flight or a workshop, so later requests
are served from the cache. It fetches every product on every range, and a failed request doesn't stop
the others:

.. code-block:: bash

    speasy cache warm amda/imf cda/AC_H0_MFI/BGSEc --range 2018-06-01 2018-06-08 --range 2019-03-01 2019-03-08
    speasy cache warm amda/imf --ranges-file storms.txt --workers 4
    speasy cache warm amda/b_mgs_mso --ranges-from amda/sharedtimeTable_37   # one range per event

A ranges file holds one ``START STOP`` (or ``START,STOP``) range per line; blank lines and ``#``
comments are ignored. ``--ranges-from`` takes a timetable or catalog product, e.g. an AMDA shared
timetable, and warms every event of it. ``--workers`` runs that many requests at the same time (one by default).

Data index
----------

The cache can expire, be evicted, or be refreshed behind your back. A data index can't: it is a folder
holding exactly the data you put in it, for a study you want to keep, take offline, or hand to someone
else. ``index fill`` takes the same products and ranges as ``cache warm``:

.. code-block:: bash

    speasy index fill ~/studies/storms amda/imf cda/AC_H0_MFI/BGSEc --ranges-from amda/sharedtimeTable_37
    speasy index info ~/studies/storms          # per product: days with data, days known to hold none
    speasy index export ~/studies/storms storms.tar
    speasy index import ~/other storms.tar      # where both hold a day, the one fetched last wins

Then use it from Python, even offline:

.. code-block:: python

    import speasy as spz
    index = spz.DataIndex("~/studies/storms")
    b = index.get_data("amda/imf", "2018-06-01", "2018-06-02")

Quicklooks
----------

``speasy quicklook`` renders a `SciQLop <https://github.com/SciQLop/SciQLop>`_ plot template as one image per
time window, without SciQLop or a display: handy for daily overview plots on a server.

.. code-block:: bash

    speasy quicklook ~/.local/share/sciqlop/templates/mms_overview.json \
        --start 2015-11-01 --stop 2015-12-01 --split daily --output-dir quicklooks/ --workers 4

``--split`` is ``daily``, ``monthly``, ``yearly`` or ``none`` (a single image), windows are aligned on the
calendar and clipped to the time range, which defaults to the one saved in the template. ``--format`` picks
the image format (``png`` by default, ``pdf``, ``svg``...), and ``--workers`` downloads that many windows at
the same time. Each image is named after the template and the window start, e.g.
``mms_overview_20151101T000000.png``.

Templates saved by SciQLop's current (v3) and previous (v2) formats are both read, as JSON or YAML. Only
speasy products on time series plots are drawn; virtual products, plugin plots and the like are listed as
skipped. Log scales come from the template, while saved axis ranges are ignored: they record one zoom level
and would clip other windows. A product that fails to download leaves its plot empty, and the command
exits with ``1``.
