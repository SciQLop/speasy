Space Physics made EASY
================================

.. toctree::
   :titlesonly:
   :hidden:
   :maxdepth: 2

   installation
   user/modules
   examples/index
   dev/index
   history
   contributing
   authors



.. image:: https://matrix.to/img/matrix-badge.svg
        :target: https://matrix.to/#/#speasy:matrix.org
        :alt: Chat on Matrix

.. image:: https://img.shields.io/pypi/v/speasy.svg
        :target: https://pypi.python.org/pypi/speasy

.. image:: https://github.com/SciQLop/speasy/workflows/Tests/badge.svg
        :target: https://github.com/SciQLop/speasy/actions?query=workflow%3A%22Tests%22

.. image:: https://readthedocs.org/projects/speasy/badge/?version=latest
        :target: https://speasy.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://codecov.io/gh/SciQLop/speasy/coverage.svg?branch=main
        :target: https://codecov.io/gh/SciQLop/speasy/branch/main
        :alt: Coverage Status

.. image:: https://img.shields.io/lgtm/alerts/g/SciQLop/speasy.svg?logo=lgtm&logoWidth=18
        :target: https://lgtm.com/projects/g/SciQLop/speasy/alerts/
        :alt: Total alerts

.. image:: https://img.shields.io/lgtm/grade/python/g/SciQLop/speasy.svg?logo=lgtm&logoWidth=18
        :target: https://lgtm.com/projects/g/SciQLop/speasy/context:python
        :alt: Language grade: Python

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.4118780.svg
   :target: https://doi.org/10.5281/zenodo.4118780
   :alt: Zendoo DOI

.. image:: https://mybinder.org/badge_logo.svg
    :target: https://mybinder.org/v2/gh/SciQLop/speasy/main?labpath=docs/examples
    :alt: Discover on MyBinder

Speasy is an open source Python client for Space Physics web services such as `CDAWEB <https://cdaweb.gsfc.nasa.gov/index.html/>`_
or `AMDA <http://amda.irap.omp.eu/>`_.
Most space physics data analysis starts with finding which server provides which dataset then figuring out how to download them.
This can be difficult specially for students or newcomers, Speasy try to remove all difficulties by providing an unique and
simple API to access them all.
Speasy aims to support as much as possible web services and also cover a maximum of features they propose.

Quickstart
----------

Installing Speasy with pip (:doc:`more details here <installation>`):

.. code-block:: console

    $ pip install speasy
    # or
    $ pip install --user speasy

Getting data is as simple as:

.. code-block:: python

    import speasy as spz
    ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")

Where amda is the webservice and imf is the product id you will get with this request.

Using the dynamic inventory this can be even simpler:

.. code-block:: python

    import speasy as spz
    amda_tree = spz.inventory.data_tree.amda
    ace_mag = spz.get_data(amda_tree.Parameters.ACE.MFI.ace_imf_all.imf, "2016-6-2", "2016-6-5")

Will produce the exact same result than previous example but has the advantage to be easier to manipulate since you can
discover available data from your favourite Python environment completion such as IPython or notebooks (might not work from IDEs).

This also works with `SSCWEB <https://sscweb.gsfc.nasa.gov/>`_, you can easily download trajectories:

.. code-block:: python

    import speasy as spz
    sscweb_tree = spz.inventory.data_tree.ssc
    solo = spz.get_data(sscweb_tree.Trajectories.solarorbiter, "2021-01-01", "2021-02-01")

Features
--------
- Simple and intuitive API (spz.get_data to get them all)
- Pandas DataFrame like interface for variables
- Quick functions to convert a variable to a Pandas DataFrame
- Local cache to avoid repeating twice the same request
- Can take advantage of SciQLop dedicated poxy as a community backed ultra fast cache
- Full support of `AMDA <http://amda.irap.omp.eu/>`_ API.

Examples
========
See :doc:`here <examples/index>` for a complete list of examples.


:doc:`Go to developers doc <dev/index>`
