AMDA
====

.. toctree::
   :maxdepth: 1

   amda_notebooks

`AMDA <http://amda.irap.omp.eu/>`_ is one of the main data providers handled by speasy. Most products are either available using directly the AMDA module or using :meth:`speasy.get_data()`.
The following documentation will focus on AMDA module specific usage.


Basics: Getting data from AMDA
------------------------------

`AMDA <http://amda.irap.omp.eu/>`_ distributes several products such as Parameters, user Parameters, Datasets, Timetables, user Timetables, Catalogs
and user Catalogs. Speasy makes them accessible thanks to this module with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_data()`
or their dedicated methods such as :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_parameter()`, :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_user_parameter()`,...
Note that you can browse the list of all available products from `AMDA <http://amda.irap.omp.eu/>`_ Workspace:

.. image:: images/AMDA_workspace_collapsed.png
   :width: 32%
   :alt: AMDA workspace collapsed
.. image:: images/AMDA_workspace_params.png
   :width: 32%
   :alt: AMDA workspace parameters
.. image:: images/AMDA_workspace_timetables.png
   :width: 32%
   :alt: AMDA workspace timetables

This module provides two kinds of operations, **list** or **get** and so user methods are prefixed with one of them.

    - **get** methods retrieve the given product from AMDA server, they takes at least the product identifier and time range for time series
    - **list** methods list available products of a given type on AMDA, they return a list of indexes that can be passed to a **get** method

Parameters
^^^^^^^^^^

Let's start with a simple example, we want to download the first parameter available on AMDA:

    >>> from speasy import amda
    >>> first_param_index=amda.list_parameters()[0]
    >>> print(first_param_index)
    <ParameterIndex: |b|>
    >>> first_param=amda.get_parameter(first_param_index, "2018-01-01", "2018-01-02")
    >>> first_param.columns
    ['imf_mag']
    >>> len(first_param.time)
    5400

Usually you already know which product you want to download, two scenarios are available:

1. You are an `AMDA <http://amda.irap.omp.eu/>`_ web interface user, so you want some specific product from AMDA Workspace. You need first to get your product id,
you will find the id from the tooltip while hovering any product (Dataset, Parameter, Timetable or Catalog):

.. image:: images/AMDA_param_id.png
   :height: 400px
   :alt: AMDA workspace id

Then simply:

    >>> from speasy import amda
    >>> mms4_fgm_btot=amda.get_parameter('mms4_b_tot', "2018-01-01", "2018-01-02")
    >>> mms4_fgm_btot.columns
    ['mms4_b_tot']
    >>> len(mms4_fgm_btot.time)
    986745

2. Second scenario, your are not much familiar with AMDA, then you can simply browse speasy dynamic inventory. In
the following example, we alias AMDA data tree as amdatree, note that Python completion works and you will be able to discover
AMDA products directly from your Python terminal or notebook:

    >>> from speasy import amda
    >>> from speasy.inventory.data_tree import amda as amdatree
    >>> mms4_fgm_btot=amda.get_parameter(amdatree.Parameters.MMS.MMS4.FGM.mms4_fgm_srvy.mms4_b_tot, "2018-01-01", "2018-01-02")
    >>> mms4_fgm_btot.columns
    ['mms4_b_tot']
    >>> len(mms4_fgm_btot.time)
    986745

See :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_parameter()` or :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_data()` for more details.


Catalogs and TimeTables
^^^^^^^^^^^^^^^^^^^^^^^

Downloading Catalogs and TimeTables from `AMDA <http://amda.irap.omp.eu/>`_ is similar to Parameters. For example let's
assume you want to download the first available catalog:

    >>> from speasy import amda
    >>> first_catalog_index=amda.list_catalogs()[0]
    >>> print(first_catalog_index)
    <CatalogIndex: model_regions_plasmas_mms_2019>
    >>> first_catalog=amda.get_catalog(first_catalog_index)
    >>> first_catalog
    <Catalog: model_regions_plasmas_mms_2019>
    >>> len(first_catalog)
    12691
    >>> print(first_catalog[1])
    <Event: 2019-01-01T00:24:04+00:00 -> 2019-01-01T00:24:04+00:00 | {'classes': '1'}>

Exactly the same with a TimeTable:

    >>> from speasy import amda
    >>> first_timetable_index=amda.list_timetables()[0]
    >>> print(first_timetable_index)
    <TimetableIndex: FTE_c1>
    >>> first_timetable=amda.get_timetable(first_timetable_index)
    >>> first_timetable
    <TimeTable: FTE_c1>
    >>> len(first_timetable)
    782
    >>> print(first_timetable[1])
    <DateTimeRange: 2001-02-02T17:29:29+00:00 -> 2001-02-02T17:29:30+00:00>


As with Parameters you can also use the ID found on `AMDA <http://amda.irap.omp.eu/>`_ web user interface:

.. image:: images/AMDA_catalog_id.png
   :height: 400px
   :alt: AMDA workspace id

Then simply:

    >>> from speasy import amda
    >>> catalog_mms_2019=amda.get_catalog("sharedcatalog_22")
    >>> catalog_mms_2019
    <Catalog: model_regions_plasmas_mms_2019>
    >>> len(catalog_mms_2019)
    12691
    >>> print(catalog_mms_2019[1])
    <Event: 2019-01-01T00:24:04+00:00 -> 2019-01-01T00:24:04+00:00 | {'classes': '1'}>

And also alternatively you can use the dynamic inventory:

    >>> from speasy import amda
    >>> from speasy.inventory.data_tree import amda as amdatree
    >>> catalog_mms_2019=amda.get_catalog(amdatree.Catalogs.SharedCatalogs.EARTH.model_regions_plasmas_mms_2019)
    >>> catalog_mms_2019
    <Catalog: model_regions_plasmas_mms_2019>
    >>> len(catalog_mms_2019)
    12691
    >>> print(catalog_mms_2019[1])
    <Event: 2019-01-01T00:24:04+00:00 -> 2019-01-01T00:24:04+00:00 | {'classes': '1'}>


Advanced: AMDA module configuration options
-------------------------------------------

AMDA user login
^^^^^^^^^^^^^^^

Most AMDA features are available without login except user created product from web user interface. You can configure
speasy to store your AMDA login, from your favourite python terminal:

    >>> from speasy import config
    >>> config.amda_username.set('my_username') # doctest: +SKIP
    >>> config.amda_password.set('my_password') # doctest: +SKIP
    >>> # check that your login/password are correctly set
    >>> config.amda_username.get(), config.amda_password.get() # doctest: +SKIP
    ('my_username', 'my_password')


Then if you correctly typed your login you should be able to list and get user products:

    >>> from speasy import amda
    >>> # list user products
    >>> amda.list_user_parameters() # doctest: +SKIP
    [<ParameterIndex: test_param>]
    >>> amda.list_user_catalogs() # doctest: +SKIP
    [<CatalogIndex: MyCatalog>]
    >>> amda.list_user_timetables() # doctest: +SKIP
    [<TimetableIndex: test_alexis>, <TimetableIndex: test_alexis2>, <TimetableIndex: tt3>]
    >>> # get my first user catalog
    >>> amda.get_user_catalog(amda.list_user_catalogs()[0]) # doctest: +SKIP
    <Catalog: MyCatalog>


AMDA cache retention
^^^^^^^^^^^^^^^^^^^^

While parameter download cache is not configurable and relies on product version to decide if local data is up to date
compared to remote data. Requests like catalogs or time-tables download have a different dedicated cache
based on duration, by default they will be cached for 15 minutes. As a consequence if a time-table has changed on AMDA servers
it might take up to the configured duration to see it.
This cache has been designed with interactive usage of speasy in mind where we want to minimize penalty of running
multiple times the same command/line.

To change this cache duration value:

    >>> from speasy import config
    >>> # set cache duration to 900 seconds
    >>> config.amda_user_cache_retention.set('900')
    >>> config.amda_user_cache_retention.get()
    '900'
