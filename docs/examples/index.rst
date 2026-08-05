Examples gallery
================

Browse example folder on MyBinder:

.. image:: https://mybinder.org/badge_logo.svg
 :target: https://mybinder.org/v2/gh/SciQLop/speasy/main?labpath=docs/examples

Browse example folder on Google Colab:

.. image:: https://colab.research.google.com/assets/colab-badge.svg
    :target: https://colab.research.google.com/github/SciQLop/speasy

New to Speasy? Start with the archive you want data from in **First steps per archive**,
then move on to **Working with data** to see what you can do with the products you fetched.

First steps per archive
-----------------------

Each of these notebooks shows how to browse one archive's inventory and fetch your first
product from it:

.. nbgallery::
   :caption: First steps per archive
   :name: first-steps-gallery

   ./AMDA
   ./CDAWeb
   ./CSA
   ./SSCWeb
   ./Cdpp3dView
   ./GenericArchive

- **AMDA** — fetch time series from the AMDA web service (a good very-first notebook).
- **CDAWeb** — browse NASA's CDAWeb inventory and plot its variables.
- **CSA** — get Cluster and Double Star data from ESA's Cluster Science Archive.
- **SSCWeb** — fetch spacecraft and body trajectories from NASA's SSCWeb.
- **Cdpp3dView** — planet and spacecraft trajectories from CDPP 3DView (disabled by default, see the notebook).
- **GenericArchive** — point Speasy at your own archive of CDF files with a small YAML description.

Working with data
-----------------

Once you can fetch data, these notebooks show Speasy's product types and analysis features:

.. nbgallery::
   :caption: Working with data
   :name: working-with-data-gallery

   ./CatalogsAndTimeTables
   ./Resampling
   ./Filtering
   ./CompleteDemo

- **CatalogsAndTimeTables** — beyond time series: catalogs, timetables and whole datasets.
- **Resampling** — resample and interpolate variables onto a common time grid.
- **Filtering** — apply scipy filters directly to Speasy variables.
- **CompleteDemo** — a longer tour combining several archives and product types.

Science reproductions and advanced examples
-------------------------------------------

Full analyses reproducing published results; they assume you are already comfortable with
the basics:

.. nbgallery::
   :caption: Science reproductions and advanced examples
   :name: science-gallery

   ./solo_epd
   ./alfvenic

- **solo_epd** — Solar Orbiter EPD/HET energetic particle fluxes.
- **alfvenic** — reproduction of the Alfvenic slow solar wind analysis from Louarn et al., 2021.

Internals
---------

.. nbgallery::
   :caption: Internals
   :name: internals-gallery

   ./Caches

- **Caches** — how Speasy's local and remote caches perform (a benchmarking notebook, not needed for normal use).
