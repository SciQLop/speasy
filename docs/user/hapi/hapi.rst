HAPI servers
============

.. toctree::
   :maxdepth: 1

`HAPI <https://hapi-server.org/>`_ (Heliophysics Application Programmer's Interface) is a standard web API for
time series data, implemented by many data centers. Speasy gives access to every server of the
`official HAPI server list <https://github.com/hapi-server/servers>`_ through a single ``hapi`` provider: each
server is a branch of ``spz.inventories.tree.hapi``, and products are named
``hapi/<server>/<dataset id>/<parameter name>``.

Basics: browsing and getting data
---------------------------------

Browse ``spz.inventories.tree.hapi`` with your python terminal completion, then pass the product you found to
:func:`speasy.get_data`:

.. code-block:: python

    import speasy as spz
    # the Dst index from the World Data Center for Geomagnetism, Kyoto
    dst = spz.get_data(spz.inventories.tree.hapi.wdc_kyoto_hapi.hour_dst.dstValue, "2024-05-10", "2024-05-13")
    # the same product, by its path
    dst = spz.get_data("hapi/wdc_kyoto_hapi/hour_dst/dstValue", "2024-05-10", "2024-05-13")

Paths use the raw HAPI dataset ids and parameter names, which may contain ``/`` or spaces, for example
``"hapi/intermagnet/aae/definitive/PT1M/native/Field_Vector"``. In the tree, each ``/`` of a dataset id is a level,
and names are made valid Python identifiers.

Each dataset only covers a finite time range, ``parameter_range()`` and ``dataset_range()`` tell you what it is:

.. code-block:: python

    spz.hapi.dataset_range("wdc_kyoto_hapi/hour_dst")
    spz.hapi.parameter_range("wdc_kyoto_hapi/hour_dst/dstValue")

All the HAPI metadata of a dataset or parameter (``cadence``, ``units``, ``description``, ``resourceURL``,
``maxRequestDuration``, …) is available as attributes of its inventory node.

What gets downloaded, and when
------------------------------

Most HAPI servers list thousands of datasets, so nothing is downloaded until you need it:

- starting the ``hapi`` provider contacts no server;
- the first time you open a server (``spz.inventories.tree.hapi.lisird``, its completion, or a ``get_data`` on one of
  its products), Speasy downloads its catalog;
- the first time you open a dataset, Speasy downloads its parameter list (``/info``).

An unreachable server only makes its own branch empty, the next access tries again.

.. note::
    Code that walks the inventory tree through ``__dict__`` sees servers and datasets that haven't been opened yet as
    empty. ``dir()``, attribute access, iteration and ``in`` load them.

Data requests longer than the dataset's ``maxRequestDuration`` (one week when the server gives none) are split, and
results are cached on disk like the other providers.

Choosing servers
----------------

CDAWeb, AMDA, CSA and SSCWeb also run HAPI servers, but Speasy already serves them natively, so they are disabled by
default to avoid listing their products twice. Servers are enabled, disabled or added in the ``[HAPI]`` section of the
configuration file, see :doc:`../configuration`:

.. code-block:: ini

    [HAPI]
    # list the native CDAWeb HAPI server too, but not KNMI
    disabled_servers = amda,csa,sscweb,knmi
    # a server missing from the official list, available as spz.inventories.tree.hapi.mylab
    extra_servers = {"mylab": "https://mylab.example.org/hapi"}

To turn HAPI off entirely, add ``hapi`` to ``disabled_providers`` (see :ref:`disabling_providers`).

The server list comes from a snapshot of the official list shipped with Speasy and refreshed with each release.
