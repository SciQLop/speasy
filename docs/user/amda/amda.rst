AMDA
====

.. toctree::
   :maxdepth: 1

   amda_products
   amda_examples
   amda_notebooks

AMDA is one of the main data providers that speasy handles. Most products are either available using directly the AMDA module or using :meth:`speasy.get_data()`.
The following documentation will focus on AMDA module specific usage.

All examples assumes that you imported AMDA module like this:

    >>> from speasy import amda

Getting data from AMDA
----------------------

`AMDA <http://amda.irap.omp.eu/>`_ distributes several products such as Parameters, user Parameters, Datasets, Timetables, user Timetables, Catalogs
and user Catalogs. Speasy makes them accessible thanks to this module with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_data()`
or their dedicated methods such as :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_parameter()`, :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_user_parameter()`,...
Note that you can browse the list of all available products from `AMDA <http://amda.irap.omp.eu/>`_ Workspace:

.. image:: images/AMDA_workspace_collapsed.png
   :width: 30%
   :alt: AMDA workspace collapsed
.. image:: images/AMDA_workspace_params.png
   :width: 30%
   :alt: AMDA workspace collapsed
.. image:: images/AMDA_workspace_timetables.png
   :width: 30%
   :alt: AMDA workspace collapsed

This module provides two kinds of operations, `list` or `get` and so user methods are prefixed with one of them.
- `get` methods retrieve the given product from AMDA server, they takes at least the product identifier and time range for time series
- `list` methods list available products of a given type on AMDA, they return a list of indexes that can be passed to a `get` method

Let's start with a simple example, we want to download the first parameter available on AMDA:

    >>> first_param_index=amda.list_parameters()[0]
    >>> first_param=amda.get_parameter(first_param_index, "2018-01-01", "2018-01-02")
    >>> first_param.columns
    ['imf_mag']
    >>> len(first_param.time)
    5400



Getting AMDA_Webservice dataset and parameters
----------------------------------------------

First import AMDA connection object::

    >>> from speasy import amda

Downloading the data is done by using the :meth:`speasy.webservices.amda.ws.AMDA_Webservice.get_data()` or :meth:`speasy.webservices.amda.ws.AMDA_Webservice.get_parameter()` methods. For example
getting `imf` data between 2000-01-01 and 2000-02-01::

    >>> parameter = amda.get_data("imf", datetime.datetime(2000,1,1), datetime.datetime(2000,2,1))
    >>> parameter
    <speasy.common.variable.SpeasyVariable object at 0x7f6c3b847bd0>

The resulting data is stored in a :class:`speasy.common.variable.SpeasyVariable` object.

The parameters data is stored as a `numpy.ndarray` object::

    >>> type(parameter.data)
    <class 'numpy.ndarray'>
    >>> parameter.data
    array([[-3.432, -3.174,  5.714],
           [-3.407, -2.763,  5.72 ],
           [-4.38 , -1.437,  5.2  ],
           ...,
           [-4.435,  0.31 , -0.27 ],
           [-4.413,  0.141, -0.247],
           [-4.335,  0.087, -0.323]])

It is also possible to get all the parameters contained in a given dataset using the :meth:`speasy.amda.amda.AMDA_Webservice.get_dataset()` method which returns a list of :class:`speasy.common.variable.SpeasyVariable` objects::

    >>> amda.get_dataset("ace-imf-all", datetime.datetime(2000,1,1), datetime.datetime(2000,2,1))
    [<speasy.common.variable.SpeasyVariable object at 0x7f79fa8f3720>, <speasy.common.variable.SpeasyVariable object at 0x7f79fa8fb950>, <speasy.common.variable.SpeasyVariable object at 0x7f79fa859540>]


Parameter time range
--------------------

Downloading data requires the user to know the desired start and end date of the data. The start and
end dates for all available datasets and parameters are available through use of the
:meth:`speasy.amda.amda.AMDA_Webservice.parameter_range()` method::

    >>> t_range = amda.parameter_range("imf")
    >>> type(t_range)
    <class 'speasy.common.datetime_range.DateTimeRange'>
    >>> t_range
    1997-09-02T00:00:12->2021-07-17T23:59:55


Listing available products
--------------------------

Users can access the list of available parameters::

   >>> parameter_list = amda.list_parameters()
   >>> dataset_list = amda.list_datasets()

You can get the list of parameters contained in a dataset with::

   >>> amda.get_dataset_parameters("ace-imf-all")
   ['imf_mag', 'imf', 'imf_gsm']


User parameters
---------------

Users with an account on AMDA_Webservice can access their private parameters. First store the users credentials
using the :class:`~speasy.config.ConfigEntry` class::

   >>> from speasy.config import ConfigEntry
   >>> ConfigEntry("AMDA_Webservice", "username").set("your_username")
   >>> ConfigEntry("AMDA_Webservice", "password").set("your_password")

The login credentials are stored locally, you only need to execute the previous lines of code once
to save the credentials. The configuration file can be found at :data:`/<user_config_dir>/speasy/config.ini`.

Parameters defined on your account can now be listed like follows::

   >>> params = amda.list_user_parameters()
   >>> for param in params:
   >>>     print(param["id"], param["name"])
   ws_0 your_first_parameter
   ws_1 your_second_parameter
   ...
   ws_n your_nth_parameter

Getting the parameter is then done with :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_parameter()`::

   >>> from datetime import datetime
   >>> start, stop = datetime(2000,1,1), datetime(2000,1,2)
   >>> param = amda.get_user_parameter("ws_0", start, stop)
   >>> param
   <speasy.common.variable.SpeasyVariable object at 0x7f8e6f31c220>
   >>> param.data
   array([[-6.156],
          [-6.15],
          [-6.088],
          ...,
          [-3.088],
          [-2.816],
          [-3.568]], dtype=object)
   >>> p.time
   array(['2001-01-01T00:00:00.000', '2001-01-01T00:00:16.000',
          '2001-01-01T00:00:32.000', ..., '2001-01-31T23:59:28.000',
          '2001-01-31T23:59:44.000', '2001-02-01T00:00:00.000'], dtype=object)

See :meth:`~speasy.amda.amda.AMDA_Webservice.list_user_parameters()` for a list of user parameter attributes.

Calling :meth:`~speasy.amda.amda.AMDA_Webservice.list_user_parameters()` or :meth:`~speasy.amda.amda.AMDA_Webservice.get_user_parameter()` will raise an :class:`~speasy.config.exception.UndefinedConfigEntry` exception if the
credentials could not be found::

   raise UndefinedConfigEntry(key1=self.key1, key2=self.key2, default=self.default)

Timetables and catalogs
-----------------------

The methods :meth:`~speasy.amda.amda.AMDA_Webservice.get_timetable` and :meth:`~speasy.amda.amda.AMDA_Webservice.get_catalog` allow you to download one of many timetables and catalogs available on AMDA_Webservice. Listing the publicly
available products is achieved through using the :meth:`~speasy.amda.amda.AMDA_Webservice.list_timetables` and :meth:`~speasy.amda.amda.AMDA_Webservice.list_catalogs` to list products by ID::

   >>> for ttid in amda.list_timetables():
   >>>     print(ttid)
   sharedtimeTable_0
   ...
   sharedtimeTable_130

You can get more information about the timetables and catalogs through the :data:`amda.timetable` and :data:`amda.catalog` attributes. These attributes are dictionaries indexed by the ID of their
respective products::

    >>> for ttid in amda.timetable:
    >>>     print(amda.timetable[ttid])
    {'xml:id': 'sharedtimeTable_139', 'id': 'sharedtimeTable_139', 'name': 'MMS_Burst_Mode_2021July', 'created': '2020-08-26T00:00:55', 'modified': '1970-01-01T00:00:00', 'surveyStart': '2021-07-01T00:03:43', 'surveyStop': '2021-07-25T13:51:53', 'contact': 'MMS_Burst_Mode_2021July', 'description': 'Time intervals for which MMS burst mode data are available. source: http://mmsburst.sr.unh.edu/', 'history': '', 'nbIntervals': '441', 'sharedBy': 'AMDA_Webservice', 'sharedDate': '2021-08-02T03:25:05+00:00', 'folder': 'MMS_BURST_MODE_timeTable', 'timeTable': 'sharedtimeTable_139'}
    ...

For a description of the :data:`timetable` and :data:`catalog` attributes see the :class:`~speasy.amda.amda.AMDA_Webservice` class documentation.



