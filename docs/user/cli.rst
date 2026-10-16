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

A ranges file holds one ``START STOP`` (or ``START,STOP``) range per line; blank lines and ``#``
comments are ignored. ``--workers`` runs that many requests at the same time (one by default).
