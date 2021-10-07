"""
speasy.amda.amda
----------------

This module contains the definition of the :class:`~speasy.amda.amda.AMDA_Webservice` class, the object that
manages the connexion to AMDA_Webservice and allows users to list available products, get informations about
that product and downloading the corresponding data.

AMDA_Webservice provides the following products :
    - parameters (:meth:`~speasy.amda.amda.AMDA_Webservice.get_parameter()`) : time-series
    - datasets (:meth:`~speasy.amda.amda.AMDA_Webservice.get_dataset()`) : collection of parameters with same time base
    - timetables (:meth:`~speasy.amda.amda.AMDA_Webservice.get_timetable()`)
    - catalogs (:meth:`~speasy.amda.amda.AMDA_Webservice.get_catalog()`)

Every product has a unique identifier, users can use the :meth:`~speasy.amda.amda.AMDA_Webservice.list_parameters()` and :meth:`~speasy.amda.amda.AMDA_Webservice.list_datasets()` methods to retrieve the list of available datasets
and parameters.


"""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

from .ws import AMDA_Webservice, ProductType
