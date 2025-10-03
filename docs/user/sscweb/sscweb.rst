Satellite Situation Center (SSCWeb)
===================================

.. toctree::
   :maxdepth: 1


`SSCWeb <https://sscweb.gsfc.nasa.gov/>`_ provides trajectories for our solar system space objects such as planets, moons and spacecrafts
in different coordinate systems. It's integration into speasy makes easy to get any available object trajectory on any time range.

Basics: Getting data from SSCWeb module
---------------------------------------

First you need to ensure that the trajectory you want to get is available with this module. The easiest solution is use
speasy dynamic inventory so you will always get an up to date inventory:

    >>> import speasy as spz
    >>> # Let's only print the first 10 objects
    >>> print(list(spz.inventories.flat_inventories.ssc.parameters.keys())[:10])
    ['ace', 'active', 'adityal1', 'aec', 'aed', 'aee', 'aerocube6a', 'aerocube6b', 'aim', 'akebono']

Note that you can also use your python terminal completion and browse `spz.inventories.data_tree.ssc.Trajectories` to find
your trajectory.
Once you have found your trajectory, you may also want to chose in which coordinates system your data will be downloaded.
The following coordinates systems are available: **geo**, **gm**, **gse**, **gsm**, **sm**, **geitod**, **geij2000**.
By default **gse** is used.
Now you can get your trajectory:

    >>> import speasy as spz
    >>> # Let's assume you wanted to get MMS1 trajectory
    >>> mms1_traj = spz.ssc.get_data(spz.inventories.data_tree.ssc.Trajectories.mms1, "2018-01-01", "2018-02-01", 'gsm')
    >>> mms1_traj.columns
    ['X', 'Y', 'Z']
    >>> mms1_traj.values
    array([[57765.7789, 39928.6469, 36127.6976],
           [57636.7873, 39912.6769, 36075.1812],
           [57507.6709, 39896.6512, 36022.4395],
           ...,
           [74135.0437,   741.7233, 27240.7339],
           [74007.2467,   795.057 , 27220.3705],
           [73879.1839,   848.3518, 27199.876 ]], shape=(44640, 3))


