<h1 align="center">
<img src="https://raw.githubusercontent.com/SciQLop/speasy/main/logo/logo_speasy.svg" width="300">
</h1><br>

# Space Physics made EASY

[![Chat on Matrix](https://img.shields.io/matrix/speasy:matrix.org)](https://matrix.to/#/#speasy:matrix.org)
[![image](https://img.shields.io/pypi/v/speasy.svg)](https://pypi.python.org/pypi/speasy)
[![image](https://github.com/SciQLop/speasy/workflows/Tests/badge.svg)](https://github.com/SciQLop/speasy/actions?query=workflow%3A%22Tests%22)
[![Documentation Status](https://readthedocs.org/projects/speasy/badge/?version=latest)](https://speasy.readthedocs.io/en/latest/?badge=latest)
[![Coverage Status](https://codecov.io/gh/SciQLop/speasy/coverage.svg?branch=main)](https://codecov.io/gh/SciQLop/speasy/branch/main)
[![CodeQL](https://github.com/SciQLop/speasy/actions/workflows/codeql.yml/badge.svg)](https://github.com/SciQLop/speasy/actions/workflows/codeql.yml)
[![Zendoo DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4118780.svg)](https://doi.org/10.5281/zenodo.4118780)
[![Discover on MyBinder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/SciQLop/speasy/main?labpath=docs/examples)
[![Discover on Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SciQLop/speasy)
[![Speasy proxy uptime (30 days)](https://img.shields.io/uptimerobot/ratio/m792771930-24b7f89c03d5090a13462b70)](http://sciqlop.lpp.polytechnique.fr/cache)

Speasy is an open source Python client for Space Physics web services
such as [CDAWEB](https://cdaweb.gsfc.nasa.gov/index.html/) or
[AMDA](http://amda.irap.omp.eu/). Most space physics data analysis
starts with finding which server provides which dataset then figuring
out how to download them. This can be difficult specially for students
or newcomers, Speasy try to remove all difficulties by providing an
unique and simple API to access them all. Speasy aims to support as much
as possible web services and also cover a maximum of features they
propose.

## Quickstart

Installing Speasy with pip ([more details
here](https://speasy.readthedocs.io/en/stable/installation.html)):

``` console
$ python -m pip install speasy
# or
$ python -m pip install --user speasy
```

Getting data is as simple as:

``` python
import speasy as spz
ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
```

Where amda is the webservice and imf is the product id you will get with
this request.

Using the dynamic inventory this can be even simpler:

``` python
import speasy as spz
amda_tree = spz.inventories.data_tree.amda
ace_mag = spz.get_data(amda_tree.Parameters.ACE.MFI.ace_imf_all.imf, "2016-6-2", "2016-6-5")
```

Will produce the exact same result than previous example but has the
advantage to be easier to manipulate since you can discover available
data from your favourite Python environment completion such as IPython
or notebooks (might not work from IDEs).

This also works with [SSCWEB](https://sscweb.gsfc.nasa.gov/), you can
easily download trajectories:

``` python
import speasy as spz
sscweb_tree = spz.inventories.data_tree.ssc
solo = spz.get_data(sscweb_tree.Trajectories.solarorbiter, "2021-01-01", "2021-02-01")
```

More complex requests like this one are supported:

``` python
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
```

### Documentation

Check out the documentation and examples at [speasy
documentation](https://speasy.readthedocs.io/en/stable/).

## Features

-   Simple and intuitive API (spz.get_data to get them all)
-   Pandas DataFrame like interface for variables
-   Quick functions to convert a variable to a Pandas DataFrame
-   Local cache to avoid repeating twice the same request
-   Can take advantage of SciQLop dedicated proxy as a community backed
    ultra fast cache
-   Full support of [AMDA](http://amda.irap.omp.eu/) API
-   Can retrieve time-series from [AMDA](http://amda.irap.omp.eu/),
    [CDAWeb](https://cdaweb.gsfc.nasa.gov/),
    [CSA](https://csa.esac.esa.int/csa-web/),
    [SSCWeb](https://sscweb.gsfc.nasa.gov/)

### Examples

See [here](https://speasy.readthedocs.io/en/stable/examples/index.html)
for a complete list of examples.

### Caveats

-   installing speasy on both python 3.7 or less and python 3.8 or plus
    at the same time doesn't work since entries stored in cache by
    python 3.8+ are not readable by python 3.7-.
-   Speasy is not a plotting package, while it provides basic plot
    features, it is not meant to produce publication ready figures.

### Credits

This package was created with
[Cookiecutter](https://github.com/audreyr/cookiecutter) and the
[audreyr/cookiecutter-pypackage](https://github.com/audreyr/cookiecutter-pypackage)
project template.

The development of speasy is supported by the
[CDPP](http://www.cdpp.eu/).
