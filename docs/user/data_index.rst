Keeping a study's data
======================

Speasy caches what it downloads, but a cache is not an archive. Its entries expire, it drops old ones
when it gets full, and it refreshes data behind your back when a server publishes a new version. That's
what you want day to day. It isn't what you want for a published study, a field trip without network,
or a dataset you hand to a colleague.

A **data index** is for that. It is a folder that holds exactly the data you put in it. It never
expires, never changes unless you ask, works offline, and can be exported as a single file.

.. list-table::
   :header-rows: 1

   * -
     - Cache
     - Data index
   * - Expires, gets evicted
     - yes
     - never
   * - Refreshed automatically
     - yes
     - only the last day of a dataset, which may still grow, at most once an hour
   * - Works offline
     - partly (see ``prefer_cache``)
     - yes, without starting any provider
   * - Can be handed to someone else
     - no
     - ``export_data`` / ``import_data``

Using one
---------

``DataIndex.get_data`` works like ``speasy.get_data``. It downloads only what the index doesn't hold yet,
and serves the rest from the folder:

.. code-block:: python

    import speasy as spz

    index = spz.DataIndex("~/studies/storms")
    b = index.get_data("amda/imf", "2018-06-01", "2018-06-08")          # downloaded and stored
    b = index.get_data("amda/imf", "2018-06-02", "2018-06-03")          # read from the folder, even offline
    gse = index.get_data("ssc/ace", "2018-06-01", "2018-06-08", coordinate_system="gse")

Options that change the data, such as a coordinate system, are part of what is stored, so each set of
options has its own entries. Cache and network options such as ``disable_proxy`` aren't.

Existing code, unchanged
------------------------

Inside a ``with`` block, plain ``spz.get_data`` goes through the index too, so a notebook becomes
reproducible without touching its calls. ``DataIndex.get_data`` takes the same arguments as
``spz.get_data`` (lists of products, lists of ranges, a timetable as the ranges...) and gives the same
products:

.. code-block:: python

    with spz.DataIndex("~/studies/storms"):
        b = spz.get_data("amda/imf", "2018-06-01", "2018-06-08")     # stored into / served from the index
        tt = spz.get_data("amda/sharedtimeTable_37")                  # timetables and catalogs too
    b = spz.get_data("amda/imf", "2018-06-01", "2018-06-08")         # after the block: back to normal

Everything ``spz.get_data`` gives is stored: time series and datasets by day, timetables and catalogs
whole. When the block ends, even on an exception,
``spz.get_data`` works as before. It only applies to the thread that entered the block: threads it
starts don't use the index.

Refreshing
----------

Nothing changes unless you ask:

.. code-block:: python

    index.get_data("amda/imf", "2018-06-01", "2018-06-08", refresh=True)   # one range
    index.update_all_data()                                               # everything
    index.update_all_data(["amda/imf"])                                   # some products

A refresh downloads again past Speasy's cache, and replaces what the index held. If the server has no
data there any more, the index won't either.

Days without data are stored too, so a gap is answered offline. If a server publishes that day later,
the index only sees it on a refresh.

Sharing
-------

.. code-block:: python

    index.export_data("storms.tar")
    spz.DataIndex("~/other").import_data("storms.tar")   # where both hold a day, the one fetched last wins

An index only holds plain data, never Python objects, so importing one from someone else runs no code.

From the command line
---------------------

``speasy index fill`` takes the same products and ranges as ``speasy cache warm``, e.g. one range per
event of an AMDA timetable. See :doc:`cli`.

.. code-block:: bash

    speasy index fill ~/studies/storms amda/imf --ranges-from amda/sharedtimeTable_37 --workers 4
    speasy index info ~/studies/storms

Limits
------

- Data is stored by whole UTC days, so a one-hour request on a fast product downloads its whole day once.
- For an AMDA template parameter, leaving ``product_inputs`` out and passing their default values store
  the data twice.
- Not available under Pyodide.
