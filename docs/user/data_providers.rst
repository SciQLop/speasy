Data Providers
==============

.. toctree::
   :titlesonly:
   :hidden:
   :maxdepth: 2

   amda/amda
   sscweb/sscweb
   cdaweb/cdaweb
   csa/csa
   cdpp3dview/cdpp3dview
   direct_archive/direct_archive
   Uiowa_eph_tool/uiowa_eph_tool.rst

Speasy provides access to the following web services:

    - :doc:`Automated Multi-Dataset Analysis (AMDA) <amda/amda>` — parameters, catalogs, and timetables from the CDPP
    - :doc:`Coordinated Data Analysis Web (CDAWeb) <cdaweb/cdaweb>` — public heliophysics data from current and past missions
    - :doc:`Cluster Science Archive (CSA) <csa/csa>` — Cluster and Double Star mission data
    - :doc:`Satellite Situation Center Web (SSCWeb) <sscweb/sscweb>` — spacecraft and planet trajectories
    - :doc:`CDPP 3DView <cdpp3dview/cdpp3dview>` — planet, spacecraft, and comet trajectories in various coordinate systems
    - :doc:`University of Iowa Cassini Ephemeris Tool (UiowaEphTool) <Uiowa_eph_tool/uiowa_eph_tool>` — Cassini, Ulysses, and Voyager trajectories

Speasy can also access data directly from local or remote archives using the :doc:`Direct Archive Access module <direct_archive/direct_archive>`.

While you can download any data with :meth:`speasy.get_data`, each web service has specificities and may expose extra
features through its dedicated module.

.. note::
    You can disable any provider by adding it to the ``disabled_providers`` list in your configuration file. See :ref:`disabling_providers`.
