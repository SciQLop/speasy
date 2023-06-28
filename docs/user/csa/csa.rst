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
    >>> c3_fgm_spin.values
    array([[  4.60300016,  13.44400024, -16.83200073],
           [  4.68400002,  12.85200024, -16.70800018],
           [  2.8599999 ,  12.79399967, -17.36199951],
           ...,
           [ 20.58600044,  -4.40700006, -29.24699974],
           [ 20.74099922,  -0.26800001, -29.07799911],
           [ 20.3560009 ,   1.05200005, -27.90399933]])



