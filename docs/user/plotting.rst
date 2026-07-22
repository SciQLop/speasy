Plotting
========

.. toctree::
   :maxdepth: 1

Every :class:`~speasy.products.variable.SpeasyVariable` has a ``.plot`` property that gives you a quick,
best-effort plot without needing to touch matplotlib directly.

.. note::
    Speasy is not a plotting package — for publication-ready figures, use matplotlib (or another plotting
    library) directly on ``variable.time``/``variable.values``.

Basic usage
-----------

Calling ``variable.plot()`` auto-detects the right kind of plot from the variable's metadata: a line plot
for regular time series, or a colormap/spectrogram if the variable's ``DISPLAY_TYPE`` metadata says
``"spectrogram"`` (as CDAWeb/AMDA spectral density products typically do).

.. code-block:: python

    import speasy as spz
    import matplotlib.pyplot as plt

    b_gse = spz.get_data("amda/imf", "2016-6-2", "2016-6-5")
    b_gse.plot()          # line plot: b_gse has no DISPLAY_TYPE=spectrogram metadata
    plt.show()

Customizing the plot
---------------------

``.plot()`` forwards extra keyword arguments to the underlying matplotlib call, and falls back to the
variable's own metadata (``.unit``, column names, axis names) whenever a label/unit isn't given explicitly:

.. code-block:: python

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    b_gse.plot(ax=ax, labels=["Bx", "By", "Bz"], units="nT", yaxis_label="Magnetic field")
    plt.show()

To plot a colormap/spectrogram explicitly (or force it even without ``DISPLAY_TYPE`` metadata), call
``.plot.colormap()`` directly; ``logy``/``logz`` (both default ``True``) control log-scaling the value
and frequency axes:

.. code-block:: python

    spectro_var.plot.colormap(logy=True, logz=True)
    plt.show()

Choosing a backend
-------------------

Matplotlib is the only bundled backend today, selected via ``variable.plot["matplotlib"]()`` (or simply
``variable.plot()``, since ``matplotlib`` is also the default when no backend is specified):

.. code-block:: python

    b_gse.plot["matplotlib"]()
    plt.show()
