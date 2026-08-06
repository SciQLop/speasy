<h1 align="center">
<img src="https://raw.githubusercontent.com/SciQLop/speasy/main/logo/logo_speasy.svg" width="300">
</h1><br>

# Space Physics made EASY

[![Chat on Matrix](https://img.shields.io/matrix/speasy:matrix.org)](https://matrix.to/#/#speasy:matrix.org)
[![image](https://img.shields.io/pypi/v/speasy.svg)](https://pypi.org/project/speasy)
[![image](https://github.com/SciQLop/speasy/workflows/Tests/badge.svg)](https://github.com/SciQLop/speasy/actions?query=workflow%3A%22Tests%22)
[![Documentation Status](https://readthedocs.org/projects/speasy/badge/?version=latest)](https://speasy.readthedocs.io/en/latest/?badge=latest)
[![Coverage Status](https://codecov.io/gh/SciQLop/speasy/coverage.svg?branch=main)](https://codecov.io/gh/SciQLop/speasy/branch/main)
[![CodeQL](https://github.com/SciQLop/speasy/actions/workflows/codeql.yml/badge.svg)](https://github.com/SciQLop/speasy/actions/workflows/codeql.yml)
[![Zenodo DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4118780.svg)](https://doi.org/10.5281/zenodo.4118780)
[![Discover on MyBinder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/SciQLop/speasy/main?labpath=docs/examples)
[![Discover on Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/SciQLop/speasy)
[![Speasy proxy uptime (30 days)](https://img.shields.io/uptimerobot/ratio/m792771930-24b7f89c03d5090a13462b70)](http://sciqlop.lpp.polytechnique.fr/cache)

Speasy is a free and open-source Python package that makes it easy to find and load space physics data from a variety of
data sources, whether it is online and public such as [CDAWEB](https://cdaweb.gsfc.nasa.gov/index.html/) and [AMDA](https://amda.cdpp.eu/),
or any described archive, local or remote.
Finding and loading data is where any science project starts. It would seem easy a priori but, considering the
diverse array of missions and instruments available nowadays, it proves to be one of the major bottlenecks,
especially for students and newcomers.
Speasy solves this problem by providing a **single, easy-to-use interface to over 70 space missions and 65,000 products**.

Don't want to write code? See our graphical interface [SciQLop](https://github.com/SciQLop/SciQLop).

## Main features

-   Simple and intuitive API (`spz.get_data(...)` to get them all)
-   Speasy variables are like Pandas DataFrames with seamless conversion to/from them (as long as the shape is compatible)
-   Speasy variables support numpy operations, [see numpy operations example below](#numpy-operations)
-   Speasy variables filtering and resampling capabilities, [see resampling example below](#resampling)
-   Also supports Catalogs, TimeTables, Events, and multi-variable Datasets
-   Local cache to avoid redundant downloads, backed by [pysciqlop-cache](https://pypi.org/project/pysciqlop-cache/) (see [notes for users upgrading from an older Speasy](https://speasy.readthedocs.io/en/latest/user/configuration.html#migrating-an-older-cache))
-   Uses the SciQLOP ultra fast community cache server (see [configuration](https://speasy.readthedocs.io/en/latest/user/configuration.html#proxy-section) to tune or disable it)
-   Full support of [AMDA](https://amda.cdpp.eu/) API
-   Can retrieve time-series from [AMDA](https://amda.cdpp.eu/) (analysis server at IRAP/CDPP),
    [CDAWeb](https://cdaweb.gsfc.nasa.gov/) (NASA/GSFC archive),
    [CSA](https://csa.esac.esa.int/csa-web/) (ESA Cluster archive) and
    [SSCWeb](https://sscweb.gsfc.nasa.gov/) (NASA orbit/trajectory service);
    see the [data providers documentation](https://speasy.readthedocs.io/en/stable/user/data_providers.html) for more.
-   Support data access from any local or remote archives described by YAML file.
-   Also available as [Speasy.jl](https://github.com/SciQLop/Speasy.jl) for Julia users

## Help us improve Speasy!

We want Speasy to be the best possible tool for space physics research. You can help us by:

- Answering our user survey [here](https://docs.google.com/forms/d/e/1FAIpQLScV12kvETk8jc4Zc4sIsHiteMHRVo5I8DiSAE8RyVdVkUaxJA/viewform?usp=sf_link).
- Reporting bugs or requesting features [here](https://github.com/SciQLop/speasy/issues/new).
- Creating or participating in discussions [here](https://github.com/SciQLop/speasy/discussions).

Your feedback is essential to making Speasy a better tool for everyone.

## Quickstart
### Installation

Speasy requires **Python 3.10 or newer**. We recommend installing it with pip inside a virtual environment
([more details here](https://speasy.readthedocs.io/en/stable/installation.html), conda works too):

``` console
$ python3 -m venv .venv
$ source .venv/bin/activate
$ python -m pip install speasy
# or, without a virtual environment:
$ python -m pip install --user speasy
```

Troubleshooting: your first `get_data` calls need internet access (data is then cached locally);
if you are behind a proxy or firewall, see the [configuration page](https://speasy.readthedocs.io/en/stable/user/configuration.html).

<!--[[[cog
# This file is the source: everything below between a cog marker comment and its matching end
# marker is generated by running `make readme` (cogapp, https://cog.readthedocs.io), which
# executes the Python shown in the visible fenced code blocks for real (live network calls to
# AMDA/CDA/SSC) and writes its actual output back in place. Never hand-edit a generated region;
# edit the run("""...""") source strings below instead and regenerate. `make readme-check`
# verifies in CI that this file matches what regenerating it would produce.
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

README_IMG_DIR = "README_files"
README_RAW_BASE_URL = "https://raw.githubusercontent.com/SciQLop/speasy/refs/heads/main"

def run(code):
    print(f"```python\n{code.strip()}\n```")
    exec(compile(code, "<readme>", "exec"), globals())

def save_and_show(name, alt):
    plt.savefig(os.path.join(README_IMG_DIR, name), bbox_inches="tight")
    plt.close("all")
    print(f"![{alt}]({README_RAW_BASE_URL}/{README_IMG_DIR}/{name})")
]]]-->
<!--[[[end]]]-->

### Examples
#### Simple request

This simple code example shows how easy it is to get data using Speasy. The code imports the Speasy package and defines a variable named ace_mag. This variable stores the data for the ACE IMF (interplanetary magnetic field) product, for the time period from June 2, 2016 to June 5, 2016. The code then uses the Speasy plot() function to plot the data.

<!--[[[cog
run("""
import speasy as spz
ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
ace_mag.plot();
""")
save_and_show("ace_mag.png", "ACE IMF")
]]]-->
```python
import speasy as spz
ace_mag = spz.get_data('amda/imf', "2016-6-2", "2016-6-5")
ace_mag.plot();
```
![ACE IMF](https://raw.githubusercontent.com/SciQLop/speasy/refs/heads/main/README_files/ace_mag.png)
<!--[[[end]]]-->

#### Using the dynamic inventory

Where `amda` is the data provider and `imf` is the product ID.

Using the dynamic inventory produces the same result as the previous example, but lets you discover available data
through tab-completion in IPython, Jupyter notebooks, or any Python environment that supports it.

You can discover product ids by browsing `spz.inventories.tree.<provider>` (e.g. `spz.inventories.tree.amda`)
with tab-completion, or programmatically via `spz.inventories.flat_inventories.<provider>`.
See the [concepts page](https://speasy.readthedocs.io/en/latest/user/concepts.html) for more details.

<!--[[[cog
run("""
import speasy as spz
amda_tree = spz.inventories.data_tree.amda
ace_mag = spz.get_data(amda_tree.Parameters.ACE.MFI.ace_imf_all.imf, "2016-6-2", "2016-6-5")
ace_mag.plot();
""")
save_and_show("ace_mag_dynamic_inventory.png", "ACE IMF")
]]]-->
```python
import speasy as spz
amda_tree = spz.inventories.data_tree.amda
ace_mag = spz.get_data(amda_tree.Parameters.ACE.MFI.ace_imf_all.imf, "2016-6-2", "2016-6-5")
ace_mag.plot();
```
![ACE IMF](https://raw.githubusercontent.com/SciQLop/speasy/refs/heads/main/README_files/ace_mag_dynamic_inventory.png)
<!--[[[end]]]-->

#### Plotting multiple time series on a single figure

This code example shows how to use Speasy to plot multiple time series of space physics data from the **MMS1** spacecraft on a single figure, with a shared x-axis. The code imports the Speasy package and the [Matplotlib](https://matplotlib.org/stable/) plotting library. It then creates a figure with six subplots, arranged in a single column. Next, it defines a list of products and axes to plot. Finally, it iterates over the list of products and axes, plotting each product on the corresponding axis. The code uses the Speasy [get_data()](https://speasy.readthedocs.io/en/latest/dev/speasy.html#speasy.get_data) function to load the data for each product, and the [replace_fillval_by_nan()](https://speasy.readthedocs.io/en/latest/dev/speasy.html#speasy.SpeasyVariable.replace_fillval_by_nan) function to replace any fill values (placeholders for missing data) with NaNs.
The products plotted here include magnetic field measurements from the FGM (fluxgate magnetometer)
instrument, expressed in GSE (a geocentric coordinate frame).

Note: Speasy may transparently fall back between access methods (direct archive, web service, community cache);
messages such as "switching to web service" are informational, not errors.

<!--[[[cog
run("""
import speasy as spz
import matplotlib.pyplot as plt

fig = plt.figure(figsize=(8, 16), layout="constrained")
gs = fig.add_gridspec(6, hspace=0, wspace=0)
axes = gs.subplots(sharex=True)

plots = [
    (spz.inventories.tree.cda.MMS.MMS1.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gse_srvy_l2_clean, axes[0]),
    (spz.inventories.tree.cda.MMS.MMS1.SCM.MMS1_SCM_SRVY_L2_SCSRVY.mms1_scm_acb_gse_scsrvy_srvy_l2 , axes[1]),
    (spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS.mms1_des_bulkv_gse_fast, axes[2]),
    (spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS.mms1_des_temppara_fast, axes[3]),
    (spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS.mms1_des_tempperp_fast, axes[3]),
    (spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS.mms1_des_energyspectr_omni_fast, axes[4]),
    (spz.inventories.tree.cda.MMS.MMS1.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_energyspectr_omni_fast, axes[5])
]

def plot_product(product, ax):
    values = spz.get_data(product, "2019-01-02T15", "2019-01-02T22")
    values.replace_fillval_by_nan().plot(ax=ax)

for p in plots:
    plot_product(p[0], p[1])
""")
save_and_show("mms1_multi_timeseries.png", "MMS1 multiple time series")
]]]-->
```python
import speasy as spz
import matplotlib.pyplot as plt

fig = plt.figure(figsize=(8, 16), layout="constrained")
gs = fig.add_gridspec(6, hspace=0, wspace=0)
axes = gs.subplots(sharex=True)

plots = [
    (spz.inventories.tree.cda.MMS.MMS1.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gse_srvy_l2_clean, axes[0]),
    (spz.inventories.tree.cda.MMS.MMS1.SCM.MMS1_SCM_SRVY_L2_SCSRVY.mms1_scm_acb_gse_scsrvy_srvy_l2 , axes[1]),
    (spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS.mms1_des_bulkv_gse_fast, axes[2]),
    (spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS.mms1_des_temppara_fast, axes[3]),
    (spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS.mms1_des_tempperp_fast, axes[3]),
    (spz.inventories.tree.cda.MMS.MMS1.DES.MMS1_FPI_FAST_L2_DES_MOMS.mms1_des_energyspectr_omni_fast, axes[4]),
    (spz.inventories.tree.cda.MMS.MMS1.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_energyspectr_omni_fast, axes[5])
]

def plot_product(product, ax):
    values = spz.get_data(product, "2019-01-02T15", "2019-01-02T22")
    values.replace_fillval_by_nan().plot(ax=ax)

for p in plots:
    plot_product(p[0], p[1])
```
![MMS1 multiple time series](https://raw.githubusercontent.com/SciQLop/speasy/refs/heads/main/README_files/mms1_multi_timeseries.png)
<!--[[[end]]]-->

#### Requesting multiple products and intervals at once

More complex requests like this one are supported:

The result is a list per product, each holding one variable per requested interval.

<!--[[[cog
run("""
import speasy as spz
products = [
    spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_vth,
    spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_pdyn,
    spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_n,
    spz.inventories.tree.cda.Wind.WIND.MFI.WI_H2_MFI.BGSE,
    spz.inventories.tree.ssc.Trajectories.wind,
]
intervals = [["2010-01-02", "2010-01-02T10"], ["2009-08-02", "2009-08-02T10"]]
data = spz.get_data(products, intervals)
""")
]]]-->
```python
import speasy as spz
products = [
    spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_vth,
    spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_pdyn,
    spz.inventories.tree.amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_n,
    spz.inventories.tree.cda.Wind.WIND.MFI.WI_H2_MFI.BGSE,
    spz.inventories.tree.ssc.Trajectories.wind,
]
intervals = [["2010-01-02", "2010-01-02T10"], ["2009-08-02", "2009-08-02T10"]]
data = spz.get_data(products, intervals)
```
<!--[[[end]]]-->

#### Numpy operations

Speasy variables support numpy operations, as shown in this example. The code imports the Speasy package and the NumPy library, and uses the Speasy [get_data()](https://speasy.readthedocs.io/en/latest/dev/speasy.html#speasy.get_data) function to load the magnetic field data for the MMS1 spacecraft for the time period from January 1, 2017 to January 1, 2017. The code then uses the NumPy [sqrt()](https://numpy.org/doc/stable/reference/generated/numpy.sqrt.html) and [sum()](https://numpy.org/doc/stable/reference/generated/numpy.sum.html) functions to compute the norm of the magnetic field vector. Finally, the code uses the NumPy [allclose()](https://numpy.org/doc/stable/reference/generated/numpy.allclose.html) function to check if the computed norm is close to the provided total magnetic field norm (Bt) values.

<!--[[[cog
run("""
import speasy as spz
import numpy as np
mms1_products = spz.inventories.tree.cda.MMS.MMS1
b = spz.get_data(mms1_products.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gsm_srvy_l2, '2017-01-01T02:00:00', '2017-01-01T02:00:15')
b.replace_fillval_by_nan(inplace=True)  # replace fill values by NaN
bt = b["Bt"]
b = b["Bx GSM", "By GSM", "Bz GSM"]
computed_norm = np.sqrt(np.sum(b ** 2, axis=1))
print(f"Type of b: {type(b)}")
print(f"Type of computed_norm: {type(computed_norm)}")
print(f"Type of bt: {type(bt)}")
print("Is the computed norm close to the provided total magnetic field norm?", bool(np.allclose(computed_norm, bt)))
""")
]]]-->
```python
import speasy as spz
import numpy as np
mms1_products = spz.inventories.tree.cda.MMS.MMS1
b = spz.get_data(mms1_products.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gsm_srvy_l2, '2017-01-01T02:00:00', '2017-01-01T02:00:15')
b.replace_fillval_by_nan(inplace=True)  # replace fill values by NaN
bt = b["Bt"]
b = b["Bx GSM", "By GSM", "Bz GSM"]
computed_norm = np.sqrt(np.sum(b ** 2, axis=1))
print(f"Type of b: {type(b)}")
print(f"Type of computed_norm: {type(computed_norm)}")
print(f"Type of bt: {type(bt)}")
print("Is the computed norm close to the provided total magnetic field norm?", bool(np.allclose(computed_norm, bt)))
```
Type of b: <class 'speasy.products.variable.SpeasyVariable'>
Type of computed_norm: <class 'speasy.products.variable.SpeasyVariable'>
Type of bt: <class 'speasy.products.variable.SpeasyVariable'>
Is the computed norm close to the provided total magnetic field norm? True
<!--[[[end]]]-->

#### Resampling

Speasy provides a simple way to filter and resample data. In this example, the code imports the Speasy package and the [Matplotlib](https://matplotlib.org/stable/) plotting library. It then uses the Speasy [get_data()](https://speasy.readthedocs.io/en/latest/dev/speasy.html#speasy.get_data) function to load the magnetic field and temperature data for the MMS1 spacecraft for the time period from January 1, 2017 to January 1, 2017. The code then uses the Speasy [interpolate()](https://speasy.readthedocs.io/en/latest/dev/speasy.signal.resampling.html#speasy.signal.resampling.interpolate) function to interpolate the temperature data to match the magnetic field data sampling rate. Finally, the code plots the magnetic field and temperature data on the same figure.

<!--[[[cog
run("""
import speasy as spz
from speasy.signal.resampling import interpolate
import matplotlib.pyplot as plt
mms1_products = spz.inventories.tree.cda.MMS.MMS1

b, Tperp, Tpara = spz.get_data(
        [
            mms1_products.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gsm_srvy_l2,
            mms1_products.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_tempperp_fast,
            mms1_products.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_temppara_fast
        ],
        '2017-01-01T02:00:00',
        '2017-01-01T02:00:15'
    )

Tperp_interp, Tpara_interp = interpolate(b, [Tperp, Tpara])

plt.figure()
ax = b.plot()
plt.plot(Tperp_interp.time, Tperp_interp.values, marker='+')
plt.plot(Tpara_interp.time, Tpara_interp.values, marker='+')
plt.tight_layout()
""")
save_and_show("resampling.png", "Resampling")
]]]-->
```python
import speasy as spz
from speasy.signal.resampling import interpolate
import matplotlib.pyplot as plt
mms1_products = spz.inventories.tree.cda.MMS.MMS1

b, Tperp, Tpara = spz.get_data(
        [
            mms1_products.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_gsm_srvy_l2,
            mms1_products.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_tempperp_fast,
            mms1_products.DIS.MMS1_FPI_FAST_L2_DIS_MOMS.mms1_dis_temppara_fast
        ],
        '2017-01-01T02:00:00',
        '2017-01-01T02:00:15'
    )

Tperp_interp, Tpara_interp = interpolate(b, [Tperp, Tpara])

plt.figure()
ax = b.plot()
plt.plot(Tperp_interp.time, Tperp_interp.values, marker='+')
plt.plot(Tpara_interp.time, Tpara_interp.values, marker='+')
plt.tight_layout()
```
![Resampling](https://raw.githubusercontent.com/SciQLop/speasy/refs/heads/main/README_files/resampling.png)
<!--[[[end]]]-->

## Documentation and examples

Check out [Speasy documentation](https://speasy.readthedocs.io/en/stable/) and [examples](https://speasy.readthedocs.io/en/latest/examples/index.html).

## Caveats

-   Speasy is not a plotting package.
    basic plotting capabilities are here for illustration purposes and making quick-and-dirty plots.
    It is not meant to produce publication ready figures, prefer using Matplotlib directly for example.

## Credits

The development of Speasy is supported by the [CDPP](http://www.cdpp.eu/).

This package was created with
[Cookiecutter](https://github.com/audreyr/cookiecutter) and the
[audreyr/cookiecutter-pypackage](https://github.com/audreyr/cookiecutter-pypackage)
project template.
