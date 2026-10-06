NumPy compatibility
===================

.. toctree::
   :maxdepth: 1

This page assumes you already have a ``SpeasyVariable`` from :func:`speasy.get_data`; see
:doc:`concepts` first if you don't have one yet.

``SpeasyVariable`` objects behave like NumPy arrays: you can use arithmetic operators, pass them to NumPy functions,
and index them with boolean masks or integer arrays. The result is always a ``SpeasyVariable`` when the shape
allows it (i.e. when the time axis is preserved), and a scalar or plain array otherwise.

Arithmetic operations
---------------------

Standard arithmetic operators (``+``, ``-``, ``*``, ``/``, ``**``) work directly on Speasy variables
and return a new ``SpeasyVariable`` with the same time axis:

    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> mag_divided_offset = ace_mag / 3 + 50
    >>> type(mag_divided_offset)
    <class 'speasy.products.variable.SpeasyVariable'>


NumPy functions
---------------

Most NumPy functions accept Speasy variables directly.

**Reduction functions** (like ``np.mean``, ``np.std``) collapse the data and return scalar values:

    >>> import speasy as spz
    >>> import numpy as np
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> mag_divided_offset = ace_mag / 3 + 50
    >>> np.mean(ace_mag) - np.mean(mag_divided_offset)
    np.float32(-49.76359)
    >>> np.std(ace_mag) / np.std(mag_divided_offset)
    np.float32(3.0)

**Per-row functions** (like ``np.linalg.norm`` with ``axis=1``) preserve the time axis and return a ``SpeasyVariable``:

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


Indexing and slicing
--------------------

**Boolean indexing** — select rows where a condition is true across all columns:

    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> ace_mag[ace_mag > 0]
    <speasy.products.variable.SpeasyVariable object at ...>
    >>> ace_mag[ace_mag > 0].shape, ace_mag.shape
    ((1157, 3), (16200, 3))

**Integer indexing** with ``np.where``:

    >>> import numpy as np
    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> ace_mag[np.where(ace_mag>0)]
    <speasy.products.variable.SpeasyVariable object at ...>
    >>> ace_mag[np.where(ace_mag>0)].shape, ace_mag.shape
    ((1157, 3), (16200, 3))

**Column selection** — select one or more columns by name:

    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> ace_mag.columns
    ['bx', 'by', 'bz']
    >>> bx = ace_mag["bx"]
    >>> bx.shape
    (16200, 1)

**Time slicing** — slice by ``np.datetime64`` or ``datetime`` objects:

    >>> import speasy as spz
    >>> import numpy as np
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> one_hour = ace_mag[np.datetime64("2016-06-02"):np.datetime64("2016-06-02T01:00:00")]
    >>> one_hour.shape[0] < ace_mag.shape[0]
    True


Pandas conversion
-----------------

You can convert a ``SpeasyVariable`` to a Pandas ``DataFrame`` and back:

    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> df = ace_mag.to_dataframe()
    >>> df.__class__.__name__
    'DataFrame'
    >>> df.shape
    (16200, 3)
    >>> back = spz.SpeasyVariable.from_dataframe(df)
    >>> back.__class__.__name__
    'SpeasyVariable'
    >>> back.shape
    (16200, 3)


xarray conversion
-----------------

With the optional ``xarray`` package (``pip install speasy[xarray]``), a ``SpeasyVariable`` converts to an
``xarray.DataArray`` and back. Dimensions and coordinates take the names of the variable axes, and ISTP
metadata becomes CF attributes (``UNITS`` becomes ``units``, ``FILLVAL`` becomes ``_FillValue``):

    >>> import speasy as spz
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> da = ace_mag.to_dataarray()
    >>> da.dims
    ('time', 'columns')
    >>> da.attrs["units"]
    'nT'
    >>> spz.SpeasyVariable.from_dataarray(da) == ace_mag
    True

``from_dataarray`` accepts dimensions in any order: the time dimension is the one indexed by datetimes,
or the one you name with ``time_dim=``. Naive times are taken as UTC. A whole ``xarray.Dataset`` converts
with ``speasy.products.Dataset.from_xarray(ds)``, which keeps the variables that have a time dimension.
