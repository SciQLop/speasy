Data providers
==============

.. toctree::
   :titlesonly:
   :hidden:
   :maxdepth: 2

   amda/amda
   sscweb/sscweb
   cdaweb/cdaweb
   csa/csa
   direct_archive/direct_archive

Speasy provides access to the following Web Services:

    - :doc:`Automated Multi-Dataset Analysis (AMDA) <amda/amda>`
    - :doc:`Satellite Situation Center Web (SSCWeb) <sscweb/sscweb>`
    - :doc:`Coordinated Data Analysis Web (CDAWeb) <cdaweb/cdaweb>`
    - :doc:`Cluster Science Archive (CSA) <csa/csa>`

Speasy can also access data directly from local or remote archives using the :doc:`direct archive access module <direct_archive/direct_archive>`

While you can download any data with :meth:`speasy.get_data`, each web service have specificities and might expose extra
features through their dedicated modules.

.. note::
    At any time, you can disable a provider by adding it to the ``disabled_providers`` list in your configuration file, see :ref:`disabling_providers`.
