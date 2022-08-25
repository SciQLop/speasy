SSCWEB
======

.. toctree::
   :maxdepth: 1


`SSCWeb <https://sscweb.gsfc.nasa.gov/>`_ provides trajectories for our solar system space objects such as planets, moons and spacecrafts
in different coordinate systems. It's integration into speasy makes easy to get any available object trajectory on any time range.

Basics: Getting data from SSCWeb module
---------------------------------------

First you need to ensure that the trajectory you want to get is available with this module. The easiest solution is use
speasy dynamic inventory so you will always get an up to date inventory:

    >>> import speasy as spz
    >>> # Let's only print the first 10 trajectories
    >>> print(list(spz.inventories.flat_inventories.ssc.parameters.keys())[:10])
    ['ace', 'active', 'aec', 'aed', 'aee', 'aerocube6a', 'aerocube6b', 'aim', 'akebono', 'alouette1']

Note that you can also use your python terminal completion and browse `spz.inventories.data_tree.ssc.Trajectories` to find
your trajectory.
Once you have found your trajectory, you may also want to chose in which coordinates system your data will be downloaded.
The following coordinates systems are available: **geo**, **gm**, **gse**, **gsm**, **sm**, **geitod**, **geij2000**.
By default **gse** is used.
Now you can get your trajectory:

    >>> import speasy as spz
    >>> # Let's assume you wanted to get MMS1 trajectory
    >>> mms1_traj = spz.ssc.get_trajectory(spz.inventories.data_tree.ssc.Trajectories.mms1, "2018-01-01", "2018-02-01", 'gsm')
    >>> mms1_traj.columns
    ['X', 'Y', 'Z']
    >>> mms1_traj.data
    <Quantity [[57765.77891127, 39928.64689416, 36127.69757491],
               [57636.78726753, 39912.67690181, 36075.18117495],
               [57507.67093183, 39896.65117739, 36022.43945697],
               ...,
               [74135.04374424,   741.72325874, 27240.73393024],
               [74007.246673  ,   795.05699457, 27220.37053627],
               [73879.18392451,   848.35181084, 27199.87604795]] km>

