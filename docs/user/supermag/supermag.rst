SuperMAG
========

.. toctree::
   :maxdepth: 1


`SuperMAG <https://supermag.jhuapl.edu>`_ is a worldwide collaboration that provides ground
magnetometer data from around 600 stations in a common coordinate system and baseline.
Speasy exposes each station as a parameter and returns its magnetic field vector (N/E/Z).

Logon
-----
The public station list is available without credentials, but downloading data requires a
free SuperMAG **logon** (a user id, no password). Set it once in your configuration:

.. code-block:: python

    import speasy as spz
    spz.config.supermag.logon.set("your_userid")

or provide it through the ``SPEASY_SUPERMAG_LOGON`` environment variable. Without a logon,
:meth:`speasy.get_data` raises ``MissingCredentials``.

Basics: getting data from the SuperMAG module
---------------------------------------------
Stations are discoverable through the Speasy dynamic inventory, under ``Stations`` keyed by
IAGA code:

.. code-block:: python

    import speasy as spz
    stations = spz.inventories.tree.supermag.Stations
    b = spz.get_data(stations.ABK, "2015-03-17", "2015-03-18")
    b.columns          # ['N', 'E', 'Z']

By default the data is returned in the local geomagnetic frame (``nez``). Pass
``coordinates="geo"`` to :meth:`speasy.get_data` to get the geographic frame instead.

Coverage range
--------------
``parameter_range`` returns the time range over which a station can be queried, as a
:class:`~speasy.core.datetime_range.DateTimeRange`:

.. code-block:: python

    import speasy as spz
    spz.supermag.parameter_range("Stations/ABK")
    # <DateTimeRange: 1975-01-01T00:00:00+00:00 -> 2100-01-01T00:00:00+00:00>

SuperMAG does not publish per-station coverage dates, instead it lists available
stations for a given time period. So every station shares the same generous
range; it only guards against absurd time requests. A request falling entirely
outside that range returns ``None`` with a warning instead of hitting the
network.
