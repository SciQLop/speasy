.. raw:: html

    <h1 align="center">
    <img src="https://raw.githubusercontent.com/SciQLop/speasy/main/logo/logo_speasy.svg" width="300">
    </h1><br>

Space Physics made EASY
=======================

.. toctree::
   :titlesonly:
   :hidden:
   :maxdepth: 2

   installation
   user/webservices
   user/configuration
   examples/index
   dev/index
   history
   contributing
   authors



.. image:: https://img.shields.io/matrix/speasy:matrix.org
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

.. image:: https://github.com/SciQLop/speasy/actions/workflows/codeql.yml/badge.svg
        :target: https://github.com/SciQLop/speasy/actions/workflows/codeql.yml
        :alt: CodeQL

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.4118780.svg
   :target: https://doi.org/10.5281/zenodo.4118780
   :alt: Zendoo DOI

.. image:: https://mybinder.org/badge_logo.svg
    :target: https://mybinder.org/v2/gh/SciQLop/speasy/main?labpath=docs/examples
    :alt: Discover on MyBinder

Speasy is an open source Python client for Space Physics web services such as `CDAWEB <https://cdaweb.gsfc.nasa.gov/index.html/>`__
or `AMDA <http://amda.irap.omp.eu/>`__.
Most space physics data analysis starts with finding which server provides which dataset then figuring out how to download them.
This can be difficult specially for students or newcomers, Speasy try to remove all difficulties by providing an unique and
simple API to access them all.
Speasy aims to support as much as possible web services and also cover a maximum of features they propose.

Quickstart
----------

Installing Speasy with pip (:doc:`more details here <installation>`):

.. code-block:: console

    $ python -m pip install speasy
    # or
    $ python -m pip install --user speasy

Getting data is as simple as:

.. code-block:: python

    import speasy as spz
    ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")

Where amda is the webservice and imf is the product id you will get with this request.

Using the dynamic inventory this can be even simpler:

.. code-block:: python

    import speasy as spz
    amda_tree = spz.inventories.data_tree.amda
    ace_mag = spz.get_data(amda_tree.Parameters.ACE.MFI.ace_imf_all.imf, "2016-6-2", "2016-6-5")

Will produce the exact same result than previous example but has the advantage to be easier to manipulate since you can
discover available data from your favourite Python environment completion such as IPython or notebooks (might not work from IDEs).

This also works with `SSCWEB <https://sscweb.gsfc.nasa.gov/>`__, you can easily download trajectories:

.. code-block:: python

    import speasy as spz
    sscweb_tree = spz.inventories.data_tree.ssc
    solo = spz.get_data(sscweb_tree.Trajectories.solarorbiter, "2021-01-01", "2021-02-01")

More complex requests like this one are supported:

.. code-block:: python

    import speasy as spz
    products = [
        spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_vth,
        spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_pdyn,
        spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_n,
        spz.inventories.tree.cda.Wind.WIND.MFI.WI_H2_MFI.BGSE,
        spz.inventories.tree.ssc.Trajectories.wind,
    ]
    intervals = [["2010-01-02", "2010-01-02T10"], ["2009-08-02", "2009-08-02T10"]]
    data = spz.get_data(products, intervals)

Features
--------
- Simple and intuitive API (spz.get_data to get them all)
- Pandas DataFrame like interface for variables
- Quick functions to convert a variable to a Pandas DataFrame
- Local cache to avoid repeating twice the same request
- Can take advantage of SciQLop dedicated proxy as a community backed ultra fast cache
- Full support of `AMDA <http://amda.irap.omp.eu/>`__ API
- Can retrieve time-series from `AMDA <http://amda.irap.omp.eu/>`__, `CDAWeb <https://cdaweb.gsfc.nasa.gov/>`__, `CSA <https://csa.esac.esa.int/csa-web/>`__, `SSCWeb <https://sscweb.gsfc.nasa.gov/>`__
- Also available as [Speasy.jl](https://github.com/SciQLop/Speasy.jl) for Julia users

Examples
========
See :doc:`here <examples/index>` for a complete list of examples.


:doc:`Go to developers doc <dev/index>`
