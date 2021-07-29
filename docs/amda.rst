AMDA
====

Getting AMDA dataset and parameters
-----------------------------------

First create a connexion to AMDA::

    >>> from speasy.amda import AMDA
    >>> amda = AMDA()

Downloading the data is done by using the :meth:`speasy.amda.amda.AMDA.get_data()` or :meth:`speasy.amda.amda.AMDA.get_parameter()` methods. For example
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

It is also possible to get all the parameters contained in a given dataset using the :meth:`speasy.amda.amda.AMDA.get_dataset()` method which returns a list of :class:`speasy.common.variable.SpeasyVariable` objects::

    >>> amda.get_dataset("ace-imf-all", datetime.datetime(2000,1,1), datetime.datetime(2000,2,1))
    [<speasy.common.variable.SpeasyVariable object at 0x7f79fa8f3720>, <speasy.common.variable.SpeasyVariable object at 0x7f79fa8fb950>, <speasy.common.variable.SpeasyVariable object at 0x7f79fa859540>]


Parameter time range
--------------------

Downloading data requires the user to know the desired start and end date of the data. The start and 
end dates for all available datasets and parameters are available through use of the 
:meth:`speasy.amda.amda.AMDA.parameter_range()` method::

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

Users with an account on AMDA can access their private parameters


