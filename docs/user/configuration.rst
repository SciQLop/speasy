Configuration
=============

Speasy can be configured through the ``config`` module, environment variables, or by editing an INI file directly.

The configuration file is an INI file located in your platform's user config directory under ``speasy/LPP/config.ini``
(e.g. ``~/.config/speasy/LPP/config.ini`` on Linux, ``~/Library/Application Support/speasy/LPP/config.ini`` on macOS).
You can also find the exact path programmatically:

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

For example, to disable AMDA and CDAWeb, add the following to the configuration file:

.. code-block:: ini

        [core]
        disabled_providers = amda,cdaweb

Or from Python:

    >>> import speasy as spz
    >>> spz.config.core.disabled_providers.set('amda,cdaweb') # doctest: +SKIP

Cache section
-------------

You can configure the cache location and maximum size (in bytes) by editing the ``cache`` section of the configuration file.
The default maximum cache size is 20 GB (20e9 bytes).

.. code-block:: ini

        [CACHE]
        path = /path/to/cache
        size = 1e9

Or from Python:

        >>> import speasy as spz
        >>> spz.config.cache.path.set('/path/to/cache') # doctest: +SKIP
        >>> spz.config.cache.size.set(1e9)              # doctest: +SKIP

Connecting behind an HTTP proxy
--------------------------------

Speasy automatically uses the ``HTTP_PROXY`` and ``HTTPS_PROXY`` environment variables if they are set.
