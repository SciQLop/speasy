"""
speasy.amda.amda
----------------

This package contains the definition of the :class:`~speasy.webservices.amda.ws.AMDA_Webservice` class, the object that
manages the connexion to `AMDA <http://amda.irap.omp.eu/>`_ and allows users to list available products, get their
description and downloading the corresponding data.

AMDA provides the following kinds products :
    - parameters, measurements as timeseries
        - list them with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_parameter()`
        - download them with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.list_parameters()`
    - datasets, collections of parameters with the same time axis
        - list them with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_dataset()`
        - download them with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.list_datasets()`
    - timetables, lists of time ranges
        - list them with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_timetable()`
        - download them with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.list_timetables()`
    - catalogs, timetables with metadata for each time range
        - list them with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.get_catalog()`
        - download them with :meth:`~speasy.webservices.amda.ws.AMDA_Webservice.list_catalogs()`

See :doc:`user documentation </user/amda/amda>` for a more accessible documentation.

Notes
-----
You should not create an instance of  :class:`~speasy.webservices.amda.ws.AMDA_Webservice` but use the `speasy.amda`
instance instead.

"""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

from .ws import AMDA_Webservice, ProductType
