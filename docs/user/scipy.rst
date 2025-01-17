SciPy compatibility
===================

.. toctree::
   :maxdepth: 1

Speasy wraps few `scipy <https://www.scipy.org/>`_ functions to provide additional functionalities such as interpolation, filtering and resampling. You can use these functions on Speasy variables.

Interpolation
-------------

You can use the :func:`speasy.signal.resampling.interpolate` function to interpolate one or more Speasy variables onto a new time base or another variable's time base.

For example, you can interpolate a variable onto a new time base:

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

Even more complex interpolations are supported, such as interpolating multiple variables onto a reference variable.

    >>> import speasy as spz
    >>> from speasy.signal import resampling
    >>> import numpy as np
    >>> mms1_products = spz.inventories.tree.cda.MMS.MMS1
    >>> b, Tperp, Tpara = spz.get_data(
    >>>    [
    >>>         mms1_products.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gsm_srvy_l2,
    >>>         mms1_products.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_tempperp_fast,
    >>>         mms1_products.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_temppara_fast
    >>>     ],
    >>>     '2017-01-01T02:00:00',
    >>>     '2017-01-01T02:00:15'
    >>> )
    >>> Tperp_interp, Tpara_interp = resampling.interpolate(b, [Tperp, Tpara])
    >>> Tperp_interp.shape, Tpara_interp.shape, b.shape
    ((240, 1), (240, 1), (240, 4))

Filtering
---------

You can use the :func:`speasy.signal.filtering.apply_sos_filter` function to apply a second-order section (SOS) filter to one or more Speasy variables.

For example, you can apply a high-pass filter to a variable:

    >>> import speasy as spz
    >>> from speasy.signal import filtering
    >>> from scipy import signal
    >>> import numpy as np
    >>> ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
    >>> my_filter = signal.butter(4, 0.1, 'high', output='sos')
    >>> ace_mag_filtered = filtering.apply_sos_filter(my_filter, signal.sosfilt, ace_mag)
    >>> ace_mag_filtered.shape
    (16200, 3)
    >>> np.mean(ace_mag), np.mean(ace_mag_filtered)
    (np.float32(0.35460728), np.float32(3.5491205e-06))
