Cluster Science Archive (CSA)
=============================

.. toctree::
   :maxdepth: 1

The `Cluster Science Archive (CSA) <https://csa.esac.esa.int/csa-web/>`_ provides access to all science and support data
from the Cluster (2000–2024) and Double Star (2004–2008) missions. Its integration into Speasy exposes the CSA's public
CEF datasets that follow the `ISTP <https://spdf.gsfc.nasa.gov/istp_guide/>`_ (International Solar-Terrestrial Physics)
conventions — the bulk of the Cluster/Double Star science data, delivered as `CDF <https://cdf.gsfc.nasa.gov/>`_
(Common Data Format) files — plus the GRMB (Geospace Region and Magnetospheric Boundary identification) dataset, which
classifies which magnetospheric region each Cluster spacecraft was travelling through. Other auxiliary and non-ISTP
products are not exposed through Speasy.

Basics: Getting data from CSA module
------------------------------------

The easiest solution is to use your python terminal completion and browse ``spz.inventories.tree.csa`` to find
your product.
Once you have found your product, then simply ask CSA module to get data for the provided time range:

    >>> import speasy as spz
    >>> # Let's assume you wanted to get 'Cluster C3, Magnetic Field Vector, spin resolution in GSE'
    >>> c3_fgm_spin = spz.csa.get_data(spz.inventories.tree.csa.Cluster.Cluster_3.FGM3.C3_CP_FGM_SPIN.B_vec_xyz_gse__C3_CP_FGM_SPIN, "2018-01-01", "2018-01-01T01")
    >>> c3_fgm_spin.columns
    ['Bx', 'By', 'Bz']
    >>> c3_fgm_spin.values.astype("float32")
    array([[  4.603,  13.444, -16.832],
           [  4.684,  12.852, -16.708],
           [  2.86 ,  12.794, -17.362],
           ...,
           [ 20.586,  -4.407, -29.247],
           [ 20.741,  -0.268, -29.078],
           [ 20.356,   1.052, -27.904]], shape=(852, 3), dtype=float32)

A product can also be named by its ``"DATASET_ID/variable_id"`` string id, and ``get_variable()``
takes the dataset and variable as separate arguments:

.. code-block:: python

    import speasy as spz
    # these two calls fetch the same product as above
    b = spz.get_data("csa/C3_CP_FGM_SPIN/B_vec_xyz_gse__C3_CP_FGM_SPIN", "2018-01-01", "2018-01-01T01")
    b = spz.csa.get_variable(dataset="C3_CP_FGM_SPIN", variable="B_vec_xyz_gse__C3_CP_FGM_SPIN",
                             start_time="2018-01-01", stop_time="2018-01-01T01")

Each dataset only covers a finite time range; ``parameter_range()`` and ``dataset_range()``
tell you what it is before you ask:

.. code-block:: python

    spz.csa.dataset_range("C3_CP_FGM_SPIN")
    spz.csa.parameter_range("C3_CP_FGM_SPIN/B_vec_xyz_gse__C3_CP_FGM_SPIN")

.. note::
    Asking for data outside a dataset's range is not an error: ``get_data()`` returns
    ``None`` and logs a warning naming the dataset's actual range.



