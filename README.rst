================================
Space Physics made EASY
================================


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

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.4118780.svg
   :target: https://doi.org/10.5281/zenodo.4118780
   :alt: Zendoo DOI

A simple Python package to deal with main Space Physics WebServices (CDA,CSA,AMDA,..).
This package was initially written to ease development of `SciQLop <https://github.com/SciQLop/SciQLop>`_ , but
now offers an intuitive and efficient access to any scientist or student who just want get spacecraft data.

As simple as:

.. code-block:: python

    import speasy as spz
    ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")

* Free software: GNU General Public License v3


Features
========

- Simple and intuitive API
- Pandas DataFrame like interface for variables
- Quick functions to convert a variable to a Pandas DataFrame
- Local cache to avoid repeating twice the same request

Examples
========
See `here <https://nbviewer.jupyter.org/github/SciQLop/speasy/blob/main/examples/demo.ipynb>`_ for a complete list of examples.

Credits
========

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
