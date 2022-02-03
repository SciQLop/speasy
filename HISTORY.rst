=======
History
=======

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
