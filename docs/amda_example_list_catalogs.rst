AMDA Example 6: listing catalogs
--------------------------------

Listing public catalogs.

.. literalinclude:: ../examples/amda_list_public_catalogs.py

Output ::

   $ python amda_list_public_catalogs.py 
   sharedcatalog_0
   ...
   sharedcatalog_130
   {'xml:id': 'sharedcatalog_16', 'id': 'sharedcatalog_16', 'name': 'vex', 'created': '2020-06-04T14:00:59', 'description': "Venus Express is a satellite optimised for studying the atmosphere of Venus, from the surface right up to the ionosphere. Launched on November 9th 2005, it arrived at Venus in April 2006 and continued operating for more than eight years. The mission ended on December 16th 2014. This catalog has been created using spice kernels provided by spdf and the JPL's orbnum tool (https://naif.jpl.nasa.gov/pub/naif/utilities/PC_Linux_64bit/orbnum.ug)", 'history': '', 'parameters': '', 'nbIntervals': '3162', 'sharedBy': 'AMDA', 'sharedDate': '2020-09-17T17:12:52+00:00', 'surveyStart': '2006-05-18T13:35:45', 'surveyStop': '2014-12-31T12:23:54', 'folder': 'SPACECRAFT_ORBIT_NUMBERS_catalog', 'catalog': 'sharedcatalog_16'}
   ...

See :ref:`amda-catalogs-label` for a description of the :data:`catalog` fields.
