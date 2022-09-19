Cluster Science Archive (CSA)
=============================

.. toctree::
   :maxdepth: 1

The `Cluster Science Archive (CSA) <https://csa.esac.esa.int/csa-web/>`_ provides access to all science and support data
of the on-going Cluster (2000- ) and Double Star (2004-2008) missions. It's integration into speasy makes easy to get any
public data from the **CSA** handling both webservice **API** and **ISTP** **CDF** files read.

Basics: Getting data from CSA module
------------------------------------

The easiest solution is to use your python terminal completion and browse `spz.inventories.data_tree.csa` to find
your product.
Once you have found your product, then simply ask CSA module to get data for the provided time range:

    >>> import speasy as spz
    >>> # Let's assume you wanted to get 'Cluster C3, Calibrated Magnetic Field WaveForm'
    >>> c3_staff = spz.csa.get_data(spz.inventories.data_tree.csa.Cluster.Cluster_3.STAFF_SC3.C3_CP_STA_CWF_ISR2.B_vec_xyz_Instrument__C3_CP_STA_CWF_ISR2, "2018-01-01", "2018-01-01T01")
    >>> c3_staff.columns
    ['Bx', 'By', 'Bz']
    >>> c3_staff.values
    array([[-0.27403101, -0.82174301,  0.92371303],
           [-0.27723601, -1.32115996,  1.08062005],
           [-0.13289499, -1.80436003,  0.579413  ],
           ...,
           [-1.80206001,  2.71304011,  3.36619997],
           [-1.84262002,  2.67682004,  3.2111001 ],
           [-1.90382004,  2.64352989,  3.0192399 ]])

