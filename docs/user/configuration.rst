Configuration
=============

Speasy is configured using the config module or setting environment variables or editing an ini file.
The default location can be found by running:

    >>> import speasy as spz
    >>> print(spz.config.SPEASY_CONFIG_FILE) # doctest: +SKIP

Speasy current configuration can be displayed by running:

    >>> import speasy as spz
    >>> spz.config.show() # doctest: +SKIP


Core section
------------

.. _disabling_providers:

Disabling data providers
~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes you may want to disable some data providers either to speed up Speasy import or because you don't need them.
This can be done by adding the provider name to the `disabled_providers` list in the configuration file.

For example, to disable AMDA and CDAWeb, add the following to the configuration file:

.. code-block:: ini

        [core]
        disabled_providers = amda,cdaweb

Or from Python:

    >>> import speasy as spz
    >>> spz.config.core.disabled_providers.set('amda,cdaweb') # doctest: +SKIP

Cache section
-------------

You can configure the cache location and maximum size by editing the `cache` section of the configuration file.

.. code-block:: ini

        [CACHE]
        path = /path/to/cache
        size = 1e9

Or from Python:

        >>> import speasy as spz
        >>> spz.config.cache.path.set('/path/to/cache') # doctest: +SKIP
        >>> spz.config.cache.size.set(1e9)              # doctest: +SKIP
