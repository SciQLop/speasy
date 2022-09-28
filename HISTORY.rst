=======
History
=======

1.0.0 (2022-09-25)
------------------

This is the first stable release of Speasy, this means that some part of the API won't change until next major release, they will only get bug fixes or backward compatible enhancements.
Since last release, a lot of new features has landed:

* now Speasy fully support AMDA, CDAWeb, SSCWeb and CSA web-services which represent around 55000 products.
* for CSA and CDAWeb uses CDF file format thanks to pycdfpp and PyISTP speeds up download and allow 2D+ data handling
* for each web-service Speasy provides an inventory of available products
* for each web-service except SSCWeb, Speasy automatically discard outdated data from local cache
* get_data function has evolved to accept many complex combination of products and time intervals
* get_data function is now part of the stable API of Speasy
* on disk cache loading algorithm has been improved and is now at least 10x faster
* (unstable) plotting API is under heavy rework and will continue to evolve in next releases but already support spectrogram plots and handles as much as possible information such as axes label or units
* by default Speasy proxy is enabled (for new fresh installs)
* SpeasyVariable object has been rewritten to better handle ND data and provide nice slicing features

From now upcoming releases will mostly fix bugs, extend plotting API and follow web-services evolution.
  
0.10.0 (2022-02-03)
-------------------

* Adds support for all AMDA products, even private ones
* Adds support for AMDA credentials
* Adds dynamic inventory for AMDA and SSC
* Adds possibility to set config values from ENV
* Drops Python 3.6 support and adds 3.10
* New API documentation using numpydoc 
* New user documentation using numpydoc
* Most code examples are tested with doctest
* Renames SSCWeb module get_orbit to get_trajectory 

0.9.1 (2021-11-25)
------------------

* Fix AMDA module bug `#24 downloading multidimensional data fails <https://github.com/SciQLop/speasy/issues/24>`_

0.9.0 (2021-07-29)
------------------

* Adds SPWC migration tool
* Rename SpwcVariable to SpeasyVariable

0.8.3 (2021-07-28)
------------------

* Package renamed from SPWC to SPEASY
* Some doc and CI improvements

0.8.2 (2021-04-20)
------------------

* sscweb trajectories are always in km

0.8.1 (2021-04-18)
------------------

* Fixes minimum request duration for sscweb

0.8.0 (2021-04-18)
------------------

* Full support for trajectories and 0.2 proxy version

0.7.2 (2020-11-13)
------------------

* ccsweb/proxy: Fix missing coordinate system parameter

0.7.1 (2020-11-13)
------------------

* Fix project URL on PyPi

0.7.0 (2020-11-13)
------------------

* SSCWEB support to get satellites trajectories.
* Few bug fixes.
* Totally disabled cdf support for now.

0.1.0 (2019-12-07)
------------------

* First release on PyPI.
