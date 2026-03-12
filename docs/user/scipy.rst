SciPy compatibility
===================

.. toctree::
   :maxdepth: 1

When working with space physics data, you often need to combine measurements from different instruments
that sample at different rates, or remove low-frequency trends from a signal. Speasy provides
ready-to-use functions for these common tasks, built on top of `SciPy <https://www.scipy.org/>`_.

All functions in ``speasy.signal`` accept one or more ``SpeasyVariable`` objects and return
``SpeasyVariable`` objects with metadata preserved.


Interpolation
-------------

Instruments on the same spacecraft often sample at different cadences (e.g. magnetic field at 16 Hz,
particle moments at 4.5 s). To compare them, you need to bring them onto a common time base.

**Interpolate onto a regular time grid:**

    >>> import speasy as spz
    >>> from speasy.signal import resampling
    >>> import numpy as np
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> ref_time = resampling.generate_time_vector("2016-6-2", "2016-6-5", np.timedelta64(5, 's'))
    >>> ref_time.shape, ace_mag.time.shape
    ((51840,), (16200,))
    >>> ace_mag_resampled = resampling.interpolate(ref_time, ace_mag)
    >>> ace_mag_resampled.shape
    (51840, 3)
    >>> bool(np.all(ace_mag_resampled.time == ref_time))
    True

**Interpolate onto another variable's time base** — useful for aligning two instruments:

    >>> import speasy as spz
    >>> from speasy.signal import resampling
    >>> import numpy as np
    >>> mms1_products = spz.inventories.tree.cda.MMS.MMS1
    >>> b, Tperp, Tpara = spz.get_data(
    ...    [
    ...         mms1_products.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gsm_srvy_l2,
    ...         mms1_products.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_tempperp_fast,
    ...         mms1_products.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_temppara_fast
    ...     ],
    ...     '2017-01-01T02:00:00',
    ...     '2017-01-01T02:00:15'
    ... )
    >>> Tperp_interp, Tpara_interp = resampling.interpolate(b, [Tperp, Tpara])
    >>> Tperp_interp.shape, Tpara_interp.shape, b.shape
    ((240, 1), (240, 1), (240, 4))

Here ``Tperp`` and ``Tpara`` (sampled at ~4.5 s) are interpolated onto the magnetic field time base (~16 Hz).
You can pass a list of variables to interpolate them all onto the same reference in one call.


Resampling
----------

If you simply want to change the sampling rate of a variable without providing an explicit time vector,
use :func:`~speasy.signal.resampling.resample`:

    >>> import speasy as spz
    >>> from speasy.signal import resampling
    >>> import numpy as np
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> ace_mag.shape
    (16200, 3)
    >>> ace_mag_5s = resampling.resample(ace_mag, np.timedelta64(5, 's'))
    >>> ace_mag_5s.shape
    (51837, 3)


Filtering
---------

You can apply any SciPy IIR filter (designed as second-order sections) to a Speasy variable.
This is useful for removing trends, isolating frequency bands, or smoothing data.

**Example: high-pass filter to remove the DC component**

    >>> import speasy as spz
    >>> from speasy.signal import filtering
    >>> from scipy import signal
    >>> import numpy as np
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> my_filter = signal.butter(4, 0.1, 'high', output='sos')
    >>> ace_mag_filtered = filtering.apply_sos_filter(my_filter, signal.sosfilt, ace_mag)
    >>> ace_mag_filtered.shape
    (16200, 3)
    >>> round(np.mean(ace_mag), 3), round(np.mean(ace_mag_filtered), 3)
    (np.float32(0.355), np.float32(0.0))

The ``apply_sos_filter`` function takes three arguments:

1. The filter coefficients (from ``scipy.signal.butter``, ``scipy.signal.cheby1``, etc. with ``output='sos'``)
2. The filter function to apply (typically ``scipy.signal.sosfilt`` or ``scipy.signal.sosfiltfilt`` for zero-phase filtering)
3. The variable(s) to filter (a single ``SpeasyVariable`` or a list of them)

.. note::
    Filtering assumes a regular time axis. If your data has gaps or irregular sampling,
    resample it first using :func:`~speasy.signal.resampling.resample` or :func:`~speasy.signal.resampling.interpolate`.
