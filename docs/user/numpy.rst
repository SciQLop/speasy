Numpy compatibility
===================

.. toctree::
   :maxdepth: 1


Speasy is compatible with `numpy <https://numpy.org/>`_ and uses it internally to perform various operations. You can also pass Speasy variables to most numpy functions.

Arithmetic operations
---------------------

For example, you can perform arithmetic operations on Speasy variables:

    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> mag_divided_offset = ace_mag / 3 + 50
    >>> type(mag_divided_offset)
    <class 'speasy.products.variable.SpeasyVariable'>


Numpy functions
---------------

You can also use numpy functions on Speasy variables, depending on the function, the result will be a Speasy variable or a scalar value:

In the following example, np.mean and np.std return scalar values:

    >>> import speasy as spz
    >>> import numpy as np
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> mag_divided_offset = ace_mag / 3 + 50
    >>> np.mean(ace_mag) - np.mean(mag_divided_offset)
    np.float32(-49.76359)
    >>> np.std(ace_mag) / np.std(mag_divided_offset)
    np.float32(3.0)

In the following example, np.linalg.norm returns a Speasy variable with the same number of rows as the input variable:

    >>> import speasy as spz
    >>> import numpy as np
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> ace_mag_total = np.linalg.norm(ace_mag, axis=1)
    >>> type(ace_mag_total)
    <class 'speasy.products.variable.SpeasyVariable'>
    >>> ace_mag.shape
    (16200, 3)
    >>> ace_mag_total.shape
    (16200, 1)


Indexing
--------

Speasy variables support several indexing methods, including boolean indexing:

    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> ace_mag[ace_mag > 0]
    <speasy.products.variable.SpeasyVariable object at ...>
    >>> ace_mag[ace_mag > 0].shape, ace_mag.shape
    ((1157, 3), (16200, 3))

You can also use integer indexing as with :meth:`numpy.where(...) <numpy.where>`:

    >>> import numpy as np
    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> ace_mag[np.where(ace_mag>0)]
    <speasy.products.variable.SpeasyVariable object at ...>
    >>> ace_mag[np.where(ace_mag>0)].shape, ace_mag.shape
    ((1157, 3), (16200, 3))
