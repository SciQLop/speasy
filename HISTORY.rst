=======
History
=======

1.2.5 (2024-04-17)
------------------

* Add python3.12 on ci by @jeandet in https://github.com/SciQLop/speasy/pull/126
* If last cache fragment is None then don't slice it by @jeandet in https://github.com/SciQLop/speasy/pull/125

1.2.4 (2024-03-12)
------------------

* [AMDA]Handles cases where timeRestriction is after stop_date by @jeandet in https://github.com/SciQLop/speasy/pull/124

1.2.3 (2024-02-22)
------------------

* Fixes https://github.com/SciQLop/speasy/issues/119 by @jeandet in https://github.com/SciQLop/speasy/pull/120
* Add support for AMDA restricted products by @jeandet in https://github.com/SciQLop/speasy/pull/118
* Automatically disable web services if they are not available by @jeandet in https://github.com/SciQLop/speasy/pull/112

1.2.2 (2023-11-28)
------------------

* Fixes https://github.com/SciQLop/speasy/issues/110, returns None instead of crash when there is no file on server by @jeandet in https://github.com/SciQLop/speasy/pull/111

1.2.1 (2023-11-07)
------------------

* Fixes non ISTP compliant files axis merging by @jeandet in https://github.com/SciQLop/speasy/pull/109

1.2.0 (2023-10-31)
------------------

* Fix old version code example in README.md by @jgieseler in https://github.com/SciQLop/speasy/pull/93
* Cdaweb and others archives direct file access by @jeandet in https://github.com/SciQLop/speasy/pull/89
* Drops Python 3.7 support and adds Python 3.11 by @jeandet in https://github.com/SciQLop/speasy/pull/97
* Switch to PyCDFpp 0.6+ by @jeandet in https://github.com/SciQLop/speasy/pull/100
* [AMDA] Uses CDF_ISTP as default by @jeandet in https://github.com/SciQLop/speasy/pull/101
* [Cache] Always use with transact(): statement with by @jeandet in https://github.com/SciQLop/speasy/pull/102
* Increase tests code coverage by @jeandet in https://github.com/SciQLop/speasy/pull/103
* Make more obvious to user that Speasy doesn't support downloading a whole dataset at once with some WS by @jeandet in https://github.com/SciQLop/speasy/pull/106
* [AMDA] Switch to https by @jeandet in https://github.com/SciQLop/speasy/pull/108
* Readme improvments by @jeandet in https://github.com/SciQLop/speasy/pull/104

1.1.2 (2023-06-01)
------------------

* New Speasy logo! by @jeandet in https://github.com/SciQLop/speasy/pull/84
* Switches readme to Markdown and removes lgtm badges (deprecated) by @jeandet in https://github.com/SciQLop/speasy/pull/85
* Reduces requests size for MMS big burst products on CDAWeb by @jeandet in https://github.com/SciQLop/speasy/pull/86
* Handles cases where labels are missing in CDAWeb generated files by @jeandet in https://github.com/SciQLop/speasy/pull/88
* Fixes AMDA CSV parser where derived parameters attributes gets overwritten by base param by @jeandet in https://github.com/SciQLop/speasy/pull/87
* Fixes #90: Uses output format value from config as fallback when requesting data from proxy for AMDA by @jeandet in https://github.com/SciQLop/speasy/pull/91

1.1.1 (2023-04-06)
------------------

* Fixes bug in v1.1.0 where AMDA CDF requests were not correctly written in cache.


1.1.0 (2023-04-06)
------------------

* Adds badges and links to Google Colab by @jeandet in https://github.com/SciQLop/speasy/pull/82
* better figure by @nicolasaunai in https://github.com/SciQLop/speasy/pull/83
* Adds bits for CDF support with AMDA server by @jeandet in https://github.com/SciQLop/speasy/pull/77

1.0.5 (2022-12-22)
------------------

* Drop LegacyVersion usage, fixes #78 by @jeandet in https://github.com/SciQLop/speasy/pull/79
* Replaces np.float by np.float64 since it was removed in numpy 1.24 by @jeandet in https://github.com/SciQLop/speasy/pull/81

1.0.4 (2022-12-05)
------------------

* [AMDA] Fix broken user product detection
* [AMDA] Add WS entry point in config
* Add tolerance for network failures
* Add option to disable webservices
* Fix cache issue with some CDF files

1.0.3 (2022-10-18)
------------------

* correct typo in README.rst
* uses cache setting also when loading inventory from proxy
* Matplotlib was accidentally working with DataContainer instead of Numpy array
* Amda csv read hardening
* also replace comma in dynamic inventory names


1.0.2 (2022-10-07)
------------------

* fixes regression on CSA inventory
* fixes rare issue on variable merge

1.0.1 (2022-10-06)
------------------

* several documentation improvements
* SpeasyVaraible can be sliced with numpy.datetime64
* comparing SpeasyVaraible with NaNs works as expected now (ignore NaNs)
* fixes cda inventory issue where some datasets were missing
* speasy loading time reduction by only downloading inventory from proxy if it has changed

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
