The SpeasyVariable
==================

When ``spz.get_data`` returns a time series, it is a :class:`~speasy.products.variable.SpeasyVariable`.
Whatever the archive, whatever the instrument, you get the same object.

Think of it as a numpy array that remembers what it holds. It knows the time of each sample, the
name of each column, the unit, and all the metadata the archive sent along. When you slice it or
compute with it, it keeps all of that up to date for you.

This page tours it, with the ACE magnetic field from AMDA as the example:

    >>> import numpy as np
    >>> import speasy as spz
    >>> b = spz.get_data("amda/imf", "2016-6-2", "2016-6-5")

What's inside
-------------

.. variable-diagram:: anatomy

A variable has three parts: a time axis, a values array, and descriptions of both.
The times are numpy ``datetime64`` values, in UTC. The values are a plain numpy array, with one row
per time and one column per component.

    >>> b.time[0]
    np.datetime64('2016-06-02T00:00:15.000000000')
    >>> b.values.shape
    (16200, 3)
    >>> b.columns
    ['bx', 'by', 'bz']
    >>> b.name, b.unit
    ('imf', 'nT')
    >>> len(b)
    16200

``b.meta`` is a dictionary with everything the archive said about the data: a description,
the fill value, the valid range, the coordinate frame, and so on. The most useful entries also have
their own attributes, like ``b.fill_value`` and ``b.valid_range``.

    >>> "FILLVAL" in b.meta
    True

Spectrograms and more dimensions
--------------------------------

Not every product is a few columns. A particle instrument gives one value per energy channel, at
each time. The values array then gets one more dimension, and the variable one more axis, which
says what each channel means.

.. variable-diagram:: spectrogram

Here are the electrons measured by MMS1, one hour of them:

    >>> mms1_des = spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS
    >>> spectro = spz.get_data(mms1_des.mms1_des_energyspectr_omni_fast,
    ...                        "2019-01-02T15", "2019-01-02T16")
    >>> spectro.values.shape        # 800 times, 32 energy channels
    (800, 32)
    >>> spectro.axes_labels         # axes[0] is always time
    ['time', 'mms1_des_energy_fast']
    >>> spectro.axes[1].unit
    'eV'
    >>> spectro.axes[1].values.shape
    (800, 32)

Here the energy axis has one row per time, because the instrument can change its energy table
during a measurement. When it can't, the axis is a single row. ``spectro.plot()`` knows the
difference and draws a spectrogram with the right energies either way.
Variables with even more dimensions, like full particle distributions, work the same way: one axis
per dimension of the values.

Selecting data
--------------

Square brackets select rows, columns, or both:

.. variable-diagram:: slicing

**By time.** Give a start and a stop, in any format ``get_data`` accepts: a string, a
``datetime``, a ``numpy.datetime64``, or seconds since 1970. Times without a time zone are UTC.

    >>> day = b["2016-06-03":"2016-06-04"]
    >>> len(day)
    5400
    >>> day.time[0]
    np.datetime64('2016-06-03T00:00:15.000000000')
    >>> day.time[-1]
    np.datetime64('2016-06-03T23:59:59.000000000')

Like ``get_data``, a time range includes its start and excludes its stop. So consecutive ranges
never share a sample, and ``b[:"2016-06-03"]`` and ``b["2016-06-03":]`` split ``b`` in two.
Leave out a bound to go to the start or the end.

**By row number.** Integers select rows by position, like in any Python sequence:

    >>> b[10:20].values.shape
    (10, 3)

**By column.** Give one column name, or a list of them:

    >>> b["bx"].values.shape
    (16200, 1)
    >>> b[["bx", "bz"]].columns
    ['bx', 'bz']

**With a test.** A boolean array keeps the rows where it is ``True``. For instance, the samples
where the field points north:

    >>> north = b[b.values[:, 2] > 0]
    >>> north.columns
    ['bx', 'by', 'bz']

Each result is a ``SpeasyVariable`` again, with the matching times, columns and metadata.

.. note::
    **A slice shares its memory with the variable it comes from.** Slicing is instant, even on big
    variables, because no data is copied. The flip side: changing values in the slice changes them in
    the source too. Call ``.copy()`` when you want independent data:

        >>> independent = b[:3].copy()
        >>> independent.values[0, 0] = 0.
        >>> round(float(b.values[0, 0]), 3)  # the source is untouched
        4.036

Cleaning
--------

Archives mark missing samples with a *fill value*, often ``-1e31``, stored right in the values.
Plain numpy statistics know nothing about it: one fill value ruins an average. Three methods deal
with it, and each returns a new variable:

- ``replace_fillval_by_nan()`` turns fill values into ``NaN``. Then use NaN-aware functions, like
  ``np.nanmean``;
- ``clamp_with_nan()`` turns values outside the valid range into ``NaN``;
- ``sanitized()`` drops every row holding a fill value, a ``NaN``, an infinity, or a value outside
  the valid range.

For example:

    >>> clean = b.replace_fillval_by_nan().clamp_with_nan()
    >>> len(b.sanitized()) <= len(b)
    True

``plot()`` already hides fill values, so a quick look doesn't need any of this.

Computing
---------

Arithmetic and numpy functions work directly on variables. The result is a variable, with the same
times:

    >>> b_magnitude = np.sqrt(np.sum(b ** 2, axis=1))
    >>> type(b_magnitude).__name__, b_magnitude.values.shape
    ('SpeasyVariable', (16200, 1))
    >>> b_magnitude.name                # the name records how it was made
    'sqrt(sum(power(imf, 2), axis=1))'
    >>> b_magnitude.unit
    'nT'

Reductions over time give plain numpy values, since there is no time left:

    >>> np.mean(b, axis=0).shape
    (3,)

See :doc:`numpy` for the full list of supported operations.

Speasy keeps the unit as a label; it does not convert anything by itself. When you want physical
units to follow your computations, ``unit_applied()`` gives the values as an
`astropy <https://docs.astropy.org/en/stable/units/>`__ quantity:

    >>> b.unit_applied().values.unit
    Unit("nT")

Putting variables together
--------------------------

Two requests for consecutive intervals join with :func:`~speasy.products.variable.merge`, which
also removes the samples they share:

    >>> from speasy.products.variable import merge
    >>> two_days = merge([b["2016-06-02":"2016-06-03"], b["2016-06-03":"2016-06-04"]])
    >>> len(two_days)
    10800

Products from different instruments rarely share their times. To combine them sample by sample,
first put one onto the other's times with :func:`~speasy.signal.resampling.interpolate`, as shown in
:doc:`scipy`.

Making your own
---------------

From a pandas DataFrame indexed by time, or an xarray DataArray with a time dimension:

    >>> df = b.to_dataframe()
    >>> rebuilt = spz.SpeasyVariable.from_dataframe(df)
    >>> rebuilt.columns
    ['bx', 'by', 'bz']

``SpeasyVariable.zeros_like(b)``, ``ones_like`` and ``empty_like`` give a variable with the same
times, columns and metadata as ``b``, ready to fill with your own values.
A :doc:`virtual product <virtual_products>` makes your own variable available through ``get_data``
like any other product.

Converting and saving
---------------------

    >>> type(b.to_dataframe()).__name__     # pandas
    'DataFrame'
    >>> type(b.to_dataarray()).__name__     # xarray, with named dimensions and coordinates
    'DataArray'
    >>> type(b.to_astropy_table()).__name__ # astropy
    'Table'

To save variables to a file, use a codec: ``"cdf"`` writes an ISTP-compliant CDF file that any CDF
tool can read. Give it a file name, or nothing to get the file's bytes:

    >>> from speasy.core.codecs import get_codec
    >>> cdf = get_codec("cdf")
    >>> data = cdf.save_variables([b])     # or save_variables([b], "imf.cdf")
    >>> cdf.load_variables(["imf"], data)["imf"].values.shape
    (16200, 3)

From the shell, ``speasy get amda/imf 2016-06-02 2016-06-05 --output imf.cdf`` does the same; see
:doc:`cli`.

Plotting
--------

``b.plot()`` draws a quick look with matplotlib: lines for components, a spectrogram for
spectrograms. See :doc:`plotting` to customize it.
