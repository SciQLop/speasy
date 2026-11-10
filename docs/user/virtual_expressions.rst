Virtual expressions
===================

A virtual expression is a virtual product written as arithmetic on inventory
products, without writing a function (see :doc:`virtual_products` for functions).

Building an expression
----------------------

Python operators applied to an inventory product build an expression. Nothing
is downloaded or computed at this stage:

    >>> import speasy as spz
    >>> B = spz.inventories.tree.cda.MMS.MMS1.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gse_srvy_l2
    >>> 10 * B + 1
    10 * cda/MMS1_FGM_SRVY_L2/mms1_fgm_b_gse_srvy_l2 + 1

The available operators are ``+``, ``-``, ``*``, ``/``, ``**``, the negation
``-B`` and ``abs(B)``. Their operands can be products, numbers or other
expressions. Comparison operators such as ``==`` do not build an expression.

Aligning two cadences
---------------------

Products can only be combined when they share the same time axis. Speasy never
aligns them silently: without a directive, requesting the expression raises
``TimeAxisMismatch``, and its message lists the products and their cadences:

    >>> from speasy.virtual_products import interpolate, register_virtual_product, resample
    >>> N = spz.inventories.tree.amda.Parameters.MMS.MMS1.FPI.fast_mode.mms1_fpi_dismoms.mms1_dis_ni
    >>> start, stop = "2016-10-10T12:00", "2016-10-10T12:10"
    >>> unaligned = register_virtual_product("virtual/demo/unaligned", 10 * B / N)
    >>> spz.get_data(unaligned, start, stop)
    Traceback (most recent call last):
        ...
    speasy.virtual_products.expression.TimeAxisMismatch: cannot combine

:func:`speasy.virtual_products.resample` puts products on one regular grid, built
from the requested time range. The time step is a number of seconds, a string
such as ``"1s"`` or ``"100ms"``, or a ``numpy.timedelta64``:

    >>> b1s, n1s = resample([B, N], "1s")

:func:`speasy.virtual_products.interpolate` puts products on the time axis of a
reference product instead:

    >>> [n_on_b] = interpolate(B, [N])

Both return a list with one element per product to align, usable in an expression:
the reference of ``interpolate`` gets no element. Both are limited to 1-D and 2-D
products: requesting an expression that aligns a spectrogram raises a ``ValueError``.

Registering and using an expression
-----------------------------------

An expression is registered like a function, and then used like any other
product:

    >>> ratio = register_virtual_product("virtual/demo/ratio", 10 * b1s / n1s)
    >>> result = spz.get_data("virtual/demo/ratio", start, stop)
    >>> result.values.shape
    (600, 4)
    >>> result.name
    'virtual/demo/ratio'
    >>> ratio(start, stop).values.shape
    (600, 4)

With ``interpolate``, the result has the time axis of the reference product:

    >>> on_b = register_virtual_product("virtual/demo/on_b", 10 * B / n_on_b)
    >>> spz.get_data(on_b, start, stop).values.shape
    (9599, 4)

Without ``labels=``, the columns of the result have generic names:

    >>> result.columns
    ['column_0', 'column_1', 'column_2', 'column_3']
    >>> labeled = register_virtual_product("virtual/demo/ratio_labeled", 10 * b1s / n1s,
    ...                                    labels=["x", "y", "z", "total"])
    >>> spz.get_data(labeled, start, stop).columns
    ['x', 'y', 'z', 'total']

Good to know
------------

- The result keeps the metadata of the leftmost product, without ``FILLVAL``,
  ``VALIDMIN`` and ``VALIDMAX``, which no longer describe the computed values.
- ``UNITS`` is kept for ``+`` and ``-`` between identical units, for a constant
  offset or scale (``B + 1``, ``10 * B``, ``B / 10``), for ``-B``, ``abs(B)``,
  ``resample`` and ``interpolate``. It is dropped otherwise. There is no unit
  algebra: give a computed unit when registering, with ``meta={"units": "m/s"}``.
- If any product of the expression has no data on the requested range, the
  result is ``None``.
- Options given to :func:`speasy.get_data`, such as ``force_refresh=True``, are
  passed on to the products of the expression. A virtual product written as a
  function does not receive them.
- A product can also be named by a ``"provider/uid"`` string, as long as it is
  combined with a product or an expression. Python handles a string combined
  only with a number itself: ``"amda/mms1_dis_ni" * 10`` repeats the string.

    >>> B + "amda/mms1_dis_ni"
    cda/MMS1_FGM_SRVY_L2/mms1_fgm_b_gse_srvy_l2 + amda/mms1_dis_ni
