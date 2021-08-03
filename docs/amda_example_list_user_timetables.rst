AMDA Example 8: listing user timetables
---------------------------------------

Listing private timetables.

.. literalinclude:: ../examples/amda_list_user_timetables.py

Output ::

   $ python amda_list_user_timetables.py 
   {'name': 'output-1', 'intervals': '389', 'id': 'tt_0'}
   {'name': 'output-12', 'intervals': '389', 'id': 'tt_1'}
   {'name': 'output-newell', 'intervals': '55446', 'id': 'tt_2'}
   {'name': 'output-newell-ext', 'intervals': '55446', 'id': 'tt_3'}

See :ref:`amda-timetables-label` for a description of the :data:`timetable` fields.
