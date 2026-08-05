.. highlight:: shell

============
Installation
============

Speasy requires **Python 3.10 or newer**.


Stable release
--------------

We recommend installing Speasy inside a virtual environment, especially on recent Linux
distributions where a plain ``pip install`` into the system Python fails with an
``externally-managed-environment`` error:

.. code-block:: console

    $ python3 -m venv .venv
    $ source .venv/bin/activate

(`Conda <https://docs.conda.io/>`_ environments work just as well if you already use them.)

To install Speasy, run this command in your terminal:

.. code-block:: console

    $ python -m pip install speasy
    # or
    $ python -m pip install --user speasy

This is the preferred method to install Speasy, as it will always install the most recent stable release.

To get a compressed local cache (smaller disk footprint), install the optional
``speasy[zstd]`` extra instead: ``python -m pip install "speasy[zstd]"``.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

Next, see the quickstart examples on the :doc:`documentation home page <index>` to load your first product.

.. _pip: https://pip.pypa.io
.. _Python installation guide: https://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

This section is for contributors or advanced users who want the development version.

The sources for Speasy can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone https://github.com/SciQLop/speasy

Or download the `tarball`_:

.. code-block:: console

    $ curl  -OL https://github.com/SciQLop/speasy/tarball/main

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ python -m pip install .

For a full development setup (editable install, test and documentation dependencies),
see the :doc:`contributing guide <contributing>`.

.. _Github repo: https://github.com/SciQLop/speasy
.. _tarball: https://github.com/SciQLop/speasy/tarball/main


Troubleshooting
---------------

- Your first ``get_data`` calls require internet access: Speasy contacts each provider's
  server to build its data inventory, which can take a few moments on first contact.
  Later calls reuse the cached inventories.
- If you are behind a corporate proxy or firewall, read the proxy sections of the
  :doc:`configuration page <user/configuration>` — in particular, Speasy only honors the
  ``HTTP_PROXY`` environment variable (not ``HTTPS_PROXY``).
- You may see cache- or proxy-related warnings the first time you import Speasy; they are
  normal and :doc:`user/configuration` explains how to adjust or silence them.
