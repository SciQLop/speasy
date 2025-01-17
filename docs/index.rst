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
   user/data_providers
   user/numpy
   user/scipy
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

.. image:: https://colab.research.google.com/assets/colab-badge.svg
    :target: https://colab.research.google.com/github/SciQLop/speasy
    :alt: Open in Colab


Speasy is a free and open-source Python package that makes it easy to find and load space physics data from a variety of
data sources, whether it is online and public such as `CDAWEB <https://cdaweb.gsfc.nasa.gov/index.html/>`__ and `AMDA <http://amda.irap.omp.eu/>`__,
or any described archive, local or remote.
This task, where any science project starts, would seem easy a priori but, considering the very
diverse array of missions and instrument nowaday available, proves to be one of the major bottleneck,
especially for students and newcomers.
Speasy solves this problem by providing a **single, easy-to-use interface to over 70 space missions and 65,000 products**.


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
    ace_mag.plot()

.. image:: ../README_files/README_2_0.png
   :width: 49%
   :alt: ACE IMF data

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
- Pandas DataFrame like interface for variables (columns, values, index)
- Quick functions to convert a variable to a Pandas DataFrame
- Dynamic inventory to discover available data from your favourite Python environment completion
- Speasy variables support :doc:`NumPy operations <user/numpy>`
- Speasy variables support :doc:`filtering, resampling, and interpolation <user/scipy>`
- Local cache to avoid redundant downloads
- Can take advantage of SciQLop dedicated proxy as a community backed ultra fast cache
- Full support of `AMDA <http://amda.irap.omp.eu/>`__ API
- Can retrieve time-series from `AMDA <http://amda.irap.omp.eu/>`__, `CDAWeb <https://cdaweb.gsfc.nasa.gov/>`__, `CSA <https://csa.esac.esa.int/csa-web/>`__, `SSCWeb <https://sscweb.gsfc.nasa.gov/>`__
- Can retrieve any data from any local or remote archive with a `simple configuration file <user/direct_archive/direct_archive>`__

Examples
========
See :doc:`here <examples/index>` for a complete list of examples.


:doc:`Go to developers doc <dev/index>`
