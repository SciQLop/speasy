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
    >>> # Let's assume you wanted to get 'Cluster C3, Magnetic Field Vector, spin resolution in GSE'
    >>> c3_fgm_spin = spz.csa.get_data(spz.inventories.data_tree.csa.Cluster.Cluster_3.FGM3.C3_CP_FGM_SPIN.B_vec_xyz_gse__C3_CP_FGM_SPIN, "2018-01-01", "2018-01-01T01")
    >>> c3_fgm_spin.columns
    ['Bx', 'By', 'Bz']
    >>> c3_fgm_spin.values.astype("float32")
    array([[  4.603,  13.444, -16.832],
           [  4.684,  12.852, -16.708],
           [  2.86 ,  12.794, -17.362],
           ...,
           [ 20.586,  -4.407, -29.247],
           [ 20.741,  -0.268, -29.078],
           [ 20.356,   1.052, -27.904]], dtype=float32)



