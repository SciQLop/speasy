Configuration
=============

Speasy can be configured through the ``config`` module, environment variables, or by editing an INI file directly.
For any entry, the environment variable (named ``SPEASY_<SECTION>_<ENTRY>``) takes precedence over the config
file, which takes precedence over the built-in default.

The configuration file is an INI file located in your platform's user config directory under ``speasy/config.ini``
(e.g. ``~/.config/speasy/config.ini`` on Linux, ``~/Library/Application Support/speasy/config.ini`` on macOS,
``%APPDATA%\LPP\speasy\config.ini`` on Windows). You can also find the exact path programmatically:

    >>> import speasy as spz
    >>> print(spz.config.SPEASY_CONFIG_FILE) # doctest: +SKIP

To display the current configuration:

    >>> import speasy as spz
    >>> spz.config.show() # doctest: +SKIP


Core section
------------

.. _disabling_providers:

Disabling data providers
~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes you may want to disable some data providers either to speed up Speasy import or because you don't need them.
This can be done by adding the provider name to the ``disabled_providers`` list in the configuration file.
By default, ``cdpp3dview`` ships disabled (its web service has known issues); every other provider is enabled.

For example, to disable AMDA and CDAWeb, add the following to the configuration file:

.. code-block:: ini

        [core]
        disabled_providers = amda,cdaweb

Or from Python:

    >>> import speasy as spz
    >>> spz.config.core.disabled_providers.set('amda,cdaweb') # doctest: +SKIP

Other core entries
~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Entry / env var
     - Default
     - Purpose
   * - ``http_rewrite_rules`` / ``SPEASY_CORE_HTTP_REWRITE_RULES``
     - ``{"https://cdaweb.gsfc.nasa.gov/pub/": "https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/"}``
     - A Python dict literal of URL prefixes to rewrite before sending requests
       (e.g. ``{"http://example.com": "http://localhost:8000"}``).
   * - ``http_user_agent`` / ``SPEASY_CORE_HTTP_USER_AGENT``
     - ``""``
     - User agent string sent with HTTP requests. Empty uses Speasy's default user agent.
   * - ``urlib_pool_size`` / ``SPEASY_CORE_URLIB_POOL_SIZE``
     - ``10``
     - Maximum number of connections to keep in the underlying ``urllib3`` connection pool.
   * - ``urlib_num_pools`` / ``SPEASY_CORE_URLIB_NUM_POOLS``
     - ``10``
     - Maximum number of connection pools kept by ``urllib3``.
   * - ``user_codecs_extra_dirs`` / ``SPEASY_CORE_USER_CODECS_EXTRA_DIRS``
     - *(empty)*
     - Comma-separated list of extra directories to scan for user-defined codecs.

.. _proxy_section:

Proxy section
-------------

Speasy can go through the `SciQLop community proxy <http://sciqlop.lpp.polytechnique.fr/cache>`_, a
caching server shared by all Speasy users that avoids redundant downloads of the same data. This is
unrelated to a corporate/network HTTP proxy — see :ref:`http_forward_proxy` below for that.

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Entry / env var
     - Default
     - Purpose
   * - ``enabled`` / ``SPEASY_PROXY_ENABLED``
     - ``True``
     - Whether to use the Speasy caching proxy at all.
   * - ``url`` / ``SPEASY_PROXY_URL``
     - ``https://sciqlop.lpp.polytechnique.fr/cache``
     - URL of the Speasy caching proxy server.

.. code-block:: ini

        [PROXY]
        enabled = true
        url = https://sciqlop.lpp.polytechnique.fr/cache

Or from Python:

    >>> import speasy as spz
    >>> spz.config.proxy.enabled.set(True) # doctest: +SKIP
    >>> spz.config.proxy.url.set('https://sciqlop.lpp.polytechnique.fr/cache') # doctest: +SKIP

Cache section
-------------

You can configure the local disk cache location and maximum size (in bytes) by editing the ``cache`` section of the configuration file.
The default maximum cache size is 20 GB (20e9 bytes).

.. code-block:: ini

        [CACHE]
        path = /path/to/cache
        size = 1e9

Or from Python:

        >>> import speasy as spz
        >>> spz.config.cache.path.set('/path/to/cache') # doctest: +SKIP
        >>> spz.config.cache.size.set(1e9)              # doctest: +SKIP

Inspecting and clearing the cache
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    >>> from speasy.core.cache import cache_len, cache_disk_size, entries, drop_item, drop_matching_entries # doctest: +SKIP
    >>> cache_len() # doctest: +SKIP
    130169
    >>> cache_disk_size() # doctest: +SKIP
    78207505517
    >>> list(entries())[:1] # doctest: +SKIP
    ['UiowaEphTool_orbits/Callisto_Cassini_Co-rotational/2010-01-01T00:00:00+00:00']
    >>> drop_item(list(entries())[0]) # doctest: +SKIP
    >>> drop_matching_entries(".*amda.*") # doctest: +SKIP
    >>> # clears every entry
    >>> drop_matching_entries(".*") # doctest: +SKIP

If your data still looks stale after clearing the cache, remember the local cache is only one layer:
the :ref:`Speasy proxy <proxy_section>` may also be serving a cached response, and provider-specific
caches (e.g. AMDA's ``user_cache_retention``) apply on top.

Cache backend and migrating from an older Speasy version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Speasy's local disk cache is backed by `pysciqlop-cache <https://pypi.org/project/pysciqlop-cache/>`_,
a native cache library, replacing the pure-Python ``diskcache`` package used in older Speasy versions.

If you had already used an older Speasy version, the first import of the new version detects your
existing ``diskcache``-format cache and migrates it automatically:

- This is a **one-time** operation and can take a few minutes for a large cache; subsequent imports are
  unaffected.
- Your old cache is renamed to ``<cache path>.diskcache.backup`` and kept alongside the new one — delete
  it yourself once you've confirmed the new cache works.
- Automatic migration needs the ``diskcache`` package installed (``pip install diskcache`` — it is no
  longer installed by default). If it isn't available, Speasy logs a warning and starts a fresh cache
  instead of migrating; your old cache is left untouched on disk and nothing is lost. Install
  ``diskcache`` and restart Python to trigger the migration whenever you're ready.

.. note::
    Speasy has no compiled ``pysciqlop-cache`` build for WASM/Pyodide (e.g. JupyterLite); on that
    platform caching is transparently disabled (a no-op cache) rather than causing an import error.

Index section
-------------

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Entry / env var
     - Default
     - Purpose
   * - ``path`` / ``SPEASY_INDEX_PATH``
     - platform user data dir + ``/index``
     - Where Speasy stores its product index database.

CDAWeb section
--------------

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Entry / env var
     - Default
     - Purpose
   * - ``inventory_data_path`` / ``SPEASY_CDAWEB_INVENTORY_DATA_PATH``
     - platform user data dir + ``/cda_inventory``
     - Where Speasy caches the CDAWeb inventory.
   * - ``preferred_access_method`` / ``SPEASY_CDAWEB_PREFERRED_ACCESS_METHOD``
     - ``BEST``
     - ``API`` to always use the REST API, ``FILE`` to always download files directly, or ``BEST``
       to let Speasy pick the fastest method likely to work for the requested product.

AMDA section
------------

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Entry / env var
     - Default
     - Purpose
   * - ``username`` / ``SPEASY_AMDA_USERNAME``
     - ``""``
     - Your AMDA username. Once set (together with ``password``), you can access your private AMDA products.
   * - ``password`` / ``SPEASY_AMDA_PASSWORD``
     - ``""``
     - Your AMDA password.
   * - ``user_cache_retention`` / ``SPEASY_AMDA_USER_CACHE_RETENTION``
     - ``900`` (15 minutes)
     - Cache retention, in seconds, for AMDA requests such as ``list_catalogs``. Only takes effect for
       processes started after the change — it is read once when Speasy imports the AMDA provider.
   * - ``max_chunk_size_days`` / ``SPEASY_AMDA_MAX_CHUNK_SIZE_DAYS``
     - ``10``
     - Maximum request duration in days; longer requests are automatically split into smaller ones.
   * - ``entry_point`` / ``SPEASY_AMDA_ENTRY_POINT``
     - ``https://amda.irap.omp.eu``
     - Base URL of the AMDA web service.
   * - ``output_format`` / ``SPEASY_AMDA_OUTPUT_FORMAT``
     - ``CDF_ISTP``
     - File format requested from AMDA. Only ``CDF_ISTP`` is supported today.

For example, from Python:

    >>> import speasy as spz
    >>> spz.config.amda.username.set('my_amda_username') # doctest: +SKIP
    >>> spz.config.amda.password.set('my_amda_password') # doctest: +SKIP

Archive section
---------------

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Entry / env var
     - Default
     - Purpose
   * - ``extra_inventory_lookup_dirs`` / ``SPEASY_ARCHIVE_EXTRA_INVENTORY_LOOKUP_DIRS``
     - *(empty)*
     - Comma-separated list of extra directories the Direct Archive provider scans for YAML inventory
       files, beyond its default user directory. See :doc:`direct_archive/direct_archive`.

Inventories section
-------------------

.. list-table::
   :widths: 25 15 60
   :header-rows: 1

   * - Entry / env var
     - Default
     - Purpose
   * - ``cache_retention_days`` / ``SPEASY_INVENTORIES_CACHE_RETENTION_DAYS``
     - ``2``
     - Maximum age, in days, Speasy keeps a provider's inventory cached before re-fetching it.

.. _http_forward_proxy:

Connecting behind an HTTP proxy
--------------------------------

If your network requires going through a forward HTTP proxy to reach the internet, Speasy honors the
standard ``HTTP_PROXY`` environment variable for its HTTP traffic. Note that ``HTTPS_PROXY`` is **not**
currently read — set ``HTTP_PROXY`` even for HTTPS requests. This is unrelated to the Speasy caching
proxy described in the `Proxy section`_ above.
