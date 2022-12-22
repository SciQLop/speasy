=======================
Space Physics made EASY
=======================


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

.. image:: https://colab.research.google.com/assets/colab-badge.svg
    :target: https://colab.research.google.com/github/SciQLop/speasy
    :alt: Discover on Google Colab

.. image:: https://img.shields.io/uptimerobot/ratio/m792771930-24b7f89c03d5090a13462b70
   :target: http://sciqlop.lpp.polytechnique.fr/cache
   :alt: Speasy proxy uptime (30 days)

Speasy is an open source Python client for Space Physics web services such as `CDAWEB <https://cdaweb.gsfc.nasa.gov/index.html/>`__
or `AMDA <http://amda.irap.omp.eu/>`__.
Most space physics data analysis starts with finding which server provides which dataset then figuring out how to download them.
This can be difficult specially for students or newcomers, Speasy try to remove all difficulties by providing an unique and
simple API to access them all.
Speasy aims to support as much as possible web services and also cover a maximum of features they propose.

Quickstart
----------

Installing Speasy with pip (`more details here <https://speasy.readthedocs.io/en/stable/installation.html>`_):

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
    amda_tree = spz.inventory.data_tree.amda
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

Documentation
=============

Check out the documentation and examples at `speasy documentation <https://speasy.readthedocs.io/en/stable/>`_.

Features
--------
- Simple and intuitive API (spz.get_data to get them all)
- Pandas DataFrame like interface for variables
- Quick functions to convert a variable to a Pandas DataFrame
- Local cache to avoid repeating twice the same request
- Can take advantage of SciQLop dedicated proxy as a community backed ultra fast cache
- Full support of `AMDA <http://amda.irap.omp.eu/>`__ API
- Can retrieve time-series from `AMDA <http://amda.irap.omp.eu/>`__, `CDAWeb <https://cdaweb.gsfc.nasa.gov/>`__, `CSA <https://csa.esac.esa.int/csa-web/>`_, `SSCWeb <https://sscweb.gsfc.nasa.gov/>`__


Examples
========
See `here <https://speasy.readthedocs.io/en/stable/examples/index.html>`_ for a complete list of examples.

Caveats
=======
- installing speasy on both python 3.7 or less and python 3.8 or plus at the same time doesn't work since entries stored in cache by python 3.8+ are not readable by python 3.7-.
- Speasy is not a plotting package, while it provides basic plot features, it is not meant to produce publication ready figures.

Credits
========

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage

The development of speasy is supported by the `CDPP <http://www.cdpp.eu/>`__.
