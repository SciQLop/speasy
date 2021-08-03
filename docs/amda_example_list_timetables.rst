AMDA Example 5: listing timetables
----------------------------------

Listing public timetables.

.. literalinclude:: ../examples/amda_list_public_timetables.py

Output ::

   $ python amda_list_public_timetables.py 
   sharedtimeTable_0
   ...
   sharedtimeTable_130
   {'xml:id': 'sharedtimeTable_139', 'id': 'sharedtimeTable_139', 'name': 'MMS_Burst_Mode_2021July', 'created': '2020-08-26T00:00:55', 'modified': '1970-01-01T00:00:00', 'surveyStart': '2021-07-01T00:03:43', 'surveyStop': '2021-07-25T13:51:53', 'contact': 'MMS_Burst_Mode_2021July', 'description': 'Time intervals for which MMS burst mode data are available. source: http://mmsburst.sr.unh.edu/', 'history': '', 'nbIntervals': '441', 'sharedBy': 'AMDA', 'sharedDate': '2021-08-02T03:25:05+00:00', 'folder': 'MMS_BURST_MODE_timeTable', 'timeTable': 'sharedtimeTable_139'}
   ...

See :ref:`amda-timetables-label` for a description of the :data:`timetable` fields.
