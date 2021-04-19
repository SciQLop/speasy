================================
Space Physics WebServices Client
================================


.. image:: https://img.shields.io/pypi/v/spwc.svg
        :target: https://pypi.python.org/pypi/spwc

.. image:: https://github.com/SciQLop/spwc/workflows/Python%20package/badge.svg
        :target: https://github.com/SciQLop/spwc/actions?query=workflow%3A%22Python+package%22

.. image:: https://readthedocs.org/projects/spwc/badge/?version=latest
        :target: https://spwc.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://codecov.io/gh/SciQLop/spwc/coverage.svg?branch=master
        :target: https://codecov.io/gh/SciQLop/spwc/branch/master
        :alt: Coverage Status

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.4118780.svg
   :target: https://doi.org/10.5281/zenodo.4118780
   :alt: Zendoo DOI

A simple Python package to deal with main Space Physics WebServices (CDA,CSA,AMDA,..).
This package was initially written to ease development of `SciQLop <https://github.com/SciQLop/SciQLop>`_ , but
now offers an intuitive and efficient access to any scientist or student who just want get spacecraft data.

As simple as:

.. code-block:: python

    import spwc
    ace_mag = spwc.get_data('amda/imf', "2016-6-2", "2016-6-5")

* Free software: GNU General Public License v3


Features
========

- Simple and intuitive API
- Pandas DataFrame like interface for variables
- Quick functions to convert a variable to a Pandas DataFrame
- Local cache to avoid repeating twice the same request

Examples
========
See `here <https://nbviewer.jupyter.org/github/SciQLop/spwc/blob/master/examples/demo.ipynb>`_ for a complete list of examples.

Credits
========

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
