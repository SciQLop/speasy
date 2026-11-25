Selecting and reducing axes
===========================

A variable with more than one axis besides time, such as a spectrogram or a particle distribution, often holds more
than one plot can show. numpy selects and reduces along its axes, and keeps the right ones: the axis reduced goes away,
the others keep their values, their bin widths (``delta_plus`` / ``delta_minus``) and the variable's unit. Speasy
adds what numpy can't do: find an axis by name, select by value, and integrate with bin widths.

.. code-block:: python

    import numpy as np
    import speasy as spz
    from speasy.signal.reduction import dimension, integrate, sel

    dist = spz.get_data("cda/MMS1_FPI_FAST_L2_DIS-DIST/mms1_dis_dist_fast", "2015-10-16T13:00", "2015-10-16T13:05")
    # values: (time, phi, theta, energy)

    dimension(dist, "phi")                       # 1: the dimension of mms1_dis_phi_fast in dist.values

Finding an axis
---------------

``dimension(var, axis)`` gives the dimension numpy's ``axis=`` wants. ``axis`` is the exact name, a part of the name
that matches a single axis (ignoring case), or a dimension. When a part matches several axes, or none, the error lists
the axes. Time is not one of them: the requested time range, or ``var[start:stop]``, selects it.

Selecting
---------

Indexing works along any dimension, as in numpy. An int drops the axis; a slice keeps part of it:

.. code-block:: python

    dist[:, 3]                                   # azimuth bin 3; the phi axis goes away
    dist[:, :, 1:3]                              # colatitude bins 1 and 2; the theta axis keeps those two
    dist["2015-10-16T13:01":"2015-10-16T13:02", :, :, 0]   # rows by time, as before

``sel`` selects by value, like xarray's ``sel``. A range is a slice or a ``[lo, hi]`` pair, in the axis unit, both
bounds included. A single value picks it, exactly or the closest with ``method="nearest"``, and drops the axis. On a
record-varying axis, such as MMS energies, the selection is made per record:

.. code-block:: python

    sel(dist, "energy", [1e3, 1e4])              # values between 1 and 10 keV (the axis unit is eV)
    sel(dist, "energy", 5e3, method="nearest")

Summing and averaging
---------------------

These are numpy's own functions, with ``axis=`` from ``dimension``. Replace fill values (``FILLVAL``) by NaN first, then
use the nan-aware functions, so that missing values count in neither the sum nor the mean:

.. code-block:: python

    d = dist.replace_fillval_by_nan()
    np.nansum(d, axis=dimension(d, "phi"))
    np.nanmean(d, axis=(dimension(d, "phi"), dimension(d, "theta")))
    np.average(d, axis=dimension(d, "theta"), weights=w)     # one weight per value of the axis

Two numpy behaviours to know:

* ``np.nansum`` gives **0** where every value is missing, not NaN. A plot then shows a value instead of a gap.
* ``np.average`` doesn't skip NaN: one missing value makes the whole average NaN. Where data can be missing, compute
  the weighted mean as ``np.nansum(x * w) / np.nansum(w * valid)``.

``keepdims=True`` is refused: a kept dimension would have no axis values.

Integrating
-----------

``integrate(var, axis, edges=None)`` sums each value times its bin width: the histogram integral, not a trapezoid
rule. It ignores NaN and fill values, and gives NaN where every value is missing. The result's unit is the variable's
times the axis'. The bin widths come from, in this order:

#. ``edges=``, one more than the axis values, when given;
#. the axis' ISTP ``DELTA_PLUS_VAR`` / ``DELTA_MINUS_VAR``, kept on the axis as ``delta_plus`` and ``delta_minus``;
#. the midpoints between its values.

When none of these works, for an unsorted axis for instance, it raises an error and asks for ``edges``.

.. code-block:: python

    integrate(np.nanmean(d, axis=(dimension(d, "phi"), dimension(d, "theta"))), "energy")

Example: an omni-directional energy spectrum
--------------------------------------------

An omni spectrum averages a distribution over its two angle axes. Missions differ in how they do it:

* Cluster CIS takes the plain mean of its angle bins:
  ``np.nanmean(d, axis=(dimension(d, "theta"), dimension(d, "phi")))``.
* MMS FPI averages over solid angle. Every azimuth bin is as wide as the others, so the mean over phi needs no weights.
  Over theta, each band weighs its solid angle, cos θ₁ - cos θ₂, computed from the axis and its bin widths:

.. code-block:: python

    d = dist.replace_fillval_by_nan()
    theta = d.axes[dimension(d, "theta")]        # colatitudes, in degrees
    w = np.cos(np.radians(theta.values - theta.delta_minus)) - np.cos(np.radians(theta.values + theta.delta_plus))
    over_phi = np.nanmean(d, axis=dimension(d, "phi"))
    omni = np.average(over_phi, axis=dimension(over_phi, "theta"), weights=w)

Once converted from phase space density to energy flux (f·v⁴/2), both match the missions' own omni spectra.
Speasy's tests check this on real data.
