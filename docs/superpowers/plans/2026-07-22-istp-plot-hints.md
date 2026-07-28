# ISTP Metadata Plot Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `SpeasyVariable.plot()` read ISTP metadata (`SCALETYP`, `FILLVAL`, `LABLAXIS`) already present on a fetched variable to pick sensible plot defaults (log/linear scale, fill-value masking, axis/colorbar labels), the same way SciQLop's `istp_hints -> PlotHints` layer does — without ever overriding something the caller explicitly asked for.

**Architecture:** A new pure-function module, `speasy/plotting/istp_hints.py`, maps a raw ISTP `meta` dict (plus a values array, for masking) to hint values. `speasy/plotting/__init__.py`'s `Plot.line()`/`Plot.colormap()` (the dataclass that already holds `values`/`axes` with `.meta`) consult these hints to fill in whatever the caller left unset, using the exact same `kwargs.pop("x", None) or <fallback>` precedence pattern the file already uses for `units`/`labels` — just with the hint slotted in as the fallback-before-hardcoded-default. `speasy/plotting/mpl_backend/__init__.py` (the actual matplotlib calls) gains one new parameter (`logy` on `line()`) to act on the resolved value; it has no knowledge of metadata or hints.

**Tech Stack:** Python 3.10+, numpy, matplotlib. Tests: pytest via `unittest.TestCase` (matches every existing file under `tests/`), no network access needed — all tests build `DataContainer`/`VariableAxis`/`VariableTimeAxis` directly with synthetic data and meta dicts.

## Global Constraints

- Priority order (confirmed by user): **explicit kwarg > ISTP-meta-derived hint > current hardcoded default.** A hint only fills in what the caller left unset; it must never win against an explicit kwarg, including an explicit falsy one (`logy=False`, `mask_fillval=False`) — use `is None` checks, never truthiness, to detect "caller didn't pass this."
- Scope is deliberately narrow: `SCALETYP` (log/linear), `FILLVAL` (mask to NaN), `LABLAXIS` (axis/colorbar label). `VALIDMIN`/`VALIDMAX` clamping is explicitly OUT of scope for this plan (real-world values are often deliberately wide sentinels like ±3.4e38 — auto-clamping risks silently hiding legitimate data; the existing opt-in `SpeasyVariable.clamp_with_nan()` stays the only way to do that).
- Do not reuse `SpeasyVariable.replace_fillval_by_nan()` — it has a known pre-existing bug (returns all-NaN for at least one real CDAWeb product) unrelated to this feature. Implement fill-masking independently as a plain, exact-equality numpy operation on raw arrays.
- FILLVAL comparison must be **exact equality**, not `np.isclose` — FILLVAL is a sentinel written verbatim by the instrument team; a real reading merely close to it must survive.
- Max line length 127 (flake8), flake8 checks are E9/F63/F7/F82 only, ruff only checks `NPY201`.
- Flit build, Python >= 3.10.

---

## File Structure

- **Create** `speasy/plotting/istp_hints.py` — pure functions: `scale_type_from_meta`, `is_log_scale`, `label_from_meta`, `mask_fill_values`. No SpeasyVariable/DataContainer dependency; operates on plain `dict` + `np.ndarray`.
- **Create** `tests/test_istp_hints.py` — unit tests for the above, no network, no matplotlib.
- **Create** `tests/test_plotting_hints.py` — wiring tests against `speasy.plotting.Plot` (the dataclass), built from synthetic `DataContainer`/`VariableAxis`/`VariableTimeAxis`, no network.
- **Modify** `speasy/plotting/__init__.py` — `Plot.line()` (lines 45-54) and `Plot.colormap()` (lines 56-70) consult the new hints.
- **Modify** `speasy/plotting/mpl_backend/__init__.py` — `Plot.line()` (lines 19-29) gains a `logy=False` parameter.
- **Modify** `tests/test_plotting.py` — one new test confirming `mpl_backend.Plot.line()`'s new `logy` param actually log-scales the axis.
- **Modify** `docs/user/plotting.rst` — short paragraph documenting the new metadata-aware defaults; regenerate `docs/user/images/plotting_spectrogram.png` (its colorbar label changes from the raw CDF variable name to the ISTP `LABLAXIS` value).

---

### Task 1: `istp_hints` pure functions

**Files:**
- Create: `speasy/plotting/istp_hints.py`
- Test: `tests/test_istp_hints.py`

**Interfaces:**
- Produces: `scale_type_from_meta(meta: dict) -> Optional[str]` (returns `"log"`, `"linear"`, or `None`), `is_log_scale(meta: dict) -> Optional[bool]`, `label_from_meta(meta: dict) -> Optional[str]`, `mask_fill_values(values: np.ndarray, meta: dict) -> np.ndarray`. These four names and signatures are consumed verbatim by Tasks 2 and 3.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_istp_hints.py
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for ISTP metadata -> plot hint mapping."""
import unittest

import numpy as np

from speasy.plotting.istp_hints import (
    is_log_scale,
    label_from_meta,
    mask_fill_values,
    scale_type_from_meta,
)


class ScaleTypeFromMeta(unittest.TestCase):
    def test_reads_scaletyp(self):
        self.assertEqual(scale_type_from_meta({"SCALETYP": "log"}), "log")
        self.assertEqual(scale_type_from_meta({"SCALETYP": "linear"}), "linear")

    def test_unwraps_single_element_list(self):
        self.assertEqual(scale_type_from_meta({"SCALETYP": ["log"]}), "log")

    def test_is_case_insensitive(self):
        self.assertEqual(scale_type_from_meta({"SCALETYP": "LOG"}), "log")

    def test_returns_none_when_absent(self):
        self.assertIsNone(scale_type_from_meta({}))

    def test_returns_none_on_unrecognized_value(self):
        self.assertIsNone(scale_type_from_meta({"SCALETYP": "banana"}))


class IsLogScale(unittest.TestCase):
    def test_true_for_log(self):
        self.assertIs(is_log_scale({"SCALETYP": "log"}), True)

    def test_false_for_linear(self):
        self.assertIs(is_log_scale({"SCALETYP": "linear"}), False)

    def test_none_when_absent(self):
        self.assertIsNone(is_log_scale({}))


class LabelFromMeta(unittest.TestCase):
    def test_reads_lablaxis(self):
        self.assertEqual(label_from_meta({"LABLAXIS": "Particle Energy Flux"}), "Particle Energy Flux")

    def test_unwraps_single_element_list(self):
        self.assertEqual(label_from_meta({"LABLAXIS": ["Bx"]}), "Bx")

    def test_returns_none_when_absent(self):
        self.assertIsNone(label_from_meta({}))


class MaskFillValues(unittest.TestCase):
    def test_replaces_exact_matches_with_nan(self):
        values = np.array([1.0, -9999.99, 3.0])
        result = mask_fill_values(values, {"FILLVAL": -9999.99})
        self.assertTrue(np.isnan(result[1]))
        self.assertEqual(result[0], 1.0)
        self.assertEqual(result[2], 3.0)

    def test_unwraps_single_element_list(self):
        values = np.array([1.0, -9999.99, 3.0])
        result = mask_fill_values(values, {"FILLVAL": [-9999.99]})
        self.assertTrue(np.isnan(result[1]))

    def test_does_not_touch_close_but_different_values(self):
        """FILLVAL is an exact sentinel -- a real reading close to it must survive."""
        values = np.array([1.0, -9999.98, 3.0])
        result = mask_fill_values(values, {"FILLVAL": -9999.99})
        self.assertEqual(result[1], -9999.98)

    def test_is_noop_when_fillval_absent(self):
        values = np.array([1.0, 2.0, 3.0])
        result = mask_fill_values(values, {})
        np.testing.assert_array_equal(result, values)

    def test_is_noop_when_fillval_is_nan(self):
        """Some providers (e.g. AMDA) report FILLVAL: [nan] -- data already uses NaN directly."""
        values = np.array([1.0, np.nan, 3.0])
        result = mask_fill_values(values, {"FILLVAL": [float("nan")]})
        self.assertTrue(np.isnan(result[1]))
        self.assertEqual(result[0], 1.0)

    def test_does_not_mutate_input(self):
        values = np.array([1.0, -9999.99, 3.0])
        mask_fill_values(values, {"FILLVAL": -9999.99})
        self.assertEqual(values[1], -9999.99)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_istp_hints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'speasy.plotting.istp_hints'`

- [ ] **Step 3: Write the implementation**

```python
# speasy/plotting/istp_hints.py
"""ISTP metadata -> plot configuration hints.

Maps ISTP attributes already present on a fetched SpeasyVariable's meta dict (SCALETYP,
FILLVAL, LABLAXIS) to plotting defaults, mirroring SciQLop's istp_hints -> PlotHints
translation. A hint only fills in what the caller left unset -- callers always let an
explicit keyword argument win.
"""
from typing import Optional

import numpy as np


def _scalar_meta(meta: dict, key: str):
    value = meta.get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def scale_type_from_meta(meta: dict) -> Optional[str]:
    """Returns 'log' or 'linear' from the ISTP SCALETYP attribute, or None if absent/unrecognized."""
    scaletyp = _scalar_meta(meta, "SCALETYP")
    if isinstance(scaletyp, str) and scaletyp.lower() in ("log", "linear"):
        return scaletyp.lower()
    return None


def is_log_scale(meta: dict) -> Optional[bool]:
    """Returns True/False from SCALETYP, or None if the metadata doesn't say."""
    scale = scale_type_from_meta(meta)
    return None if scale is None else scale == "log"


def label_from_meta(meta: dict) -> Optional[str]:
    """Returns the ISTP LABLAXIS attribute, or None if absent."""
    label = _scalar_meta(meta, "LABLAXIS")
    return label if isinstance(label, str) and label else None


def mask_fill_values(values: np.ndarray, meta: dict) -> np.ndarray:
    """Returns a copy of values with FILLVAL entries replaced by NaN.

    No-op if FILLVAL is absent, or if FILLVAL is itself NaN (some providers, e.g. AMDA,
    use NaN directly as the fill sentinel, so there's nothing left to mask).
    """
    fillval = _scalar_meta(meta, "FILLVAL")
    if fillval is None or (isinstance(fillval, float) and np.isnan(fillval)):
        return values
    return np.where(values == fillval, np.nan, values)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_istp_hints.py -v`
Expected: PASS (16 tests)

- [ ] **Step 5: Commit**

```bash
git add speasy/plotting/istp_hints.py tests/test_istp_hints.py
git commit -m "feat: add ISTP metadata -> plot hint mapping functions"
```

---

### Task 2: Wire hints into line plots

**Files:**
- Modify: `speasy/plotting/mpl_backend/__init__.py:19-29`
- Modify: `speasy/plotting/__init__.py:1-12` (imports), `:45-54` (`Plot.line`)
- Modify: `tests/test_plotting.py` (add one test to `MplBackendLine`)
- Create: `tests/test_plotting_hints.py` (line-plot section; colormap section added in Task 3)

**Interfaces:**
- Consumes: `is_log_scale`, `label_from_meta`, `mask_fill_values` from Task 1's `speasy/plotting/istp_hints.py`.
- Produces: `mpl_backend.Plot.line(..., logy=False, ...)` — new parameter, `speasy.plotting.Plot.line()` accepting the same `logy`/`mask_fillval` kwargs as any other forwarded matplotlib kwarg (via `**kwargs`), consumed by Task 3's tests only by pattern-reuse, not by import.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_plotting.py`, inside `class MplBackendLine`:

```python
    def test_logy_true_log_scales_the_axis(self):
        x = np.arange(10)
        y = np.arange(10) + 1.0

        ax = Plot().line(x, y, logy=True)

        self.assertEqual(ax.get_yscale(), "log")

    def test_logy_false_keeps_linear_axis(self):
        x = np.arange(10)
        y = np.arange(10) + 1.0

        ax = Plot().line(x, y, logy=False)

        self.assertEqual(ax.get_yscale(), "linear")
```

Create `tests/test_plotting_hints.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests that speasy.plotting.Plot wires ISTP metadata hints into plot defaults,
with explicit kwargs always taking precedence over a hint."""
import unittest

import matplotlib.pyplot as plt
import numpy as np

from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.plotting import Plot

_TIME = np.array(["2020-01-01", "2020-01-02", "2020-01-03"], dtype="datetime64[ns]")


def _line_plot(values_meta=None, values_array=None):
    values = np.array([1.0, 2.0, 3.0]) if values_array is None else values_array
    return Plot(
        axes=[VariableTimeAxis(values=_TIME)],
        values=DataContainer(values=values, meta=values_meta or {}, name="raw_name"),
        columns_names=["value"],
    )


class LineHints(unittest.TestCase):
    def setUp(self):
        self.addCleanup(plt.close, "all")

    def test_uses_scaletyp_hint_for_logy_when_not_explicit(self):
        ax = _line_plot(values_meta={"SCALETYP": "log"}).line()
        self.assertEqual(ax.get_yscale(), "log")

    def test_explicit_logy_overrides_scaletyp_hint(self):
        ax = _line_plot(values_meta={"SCALETYP": "log"}).line(logy=False)
        self.assertEqual(ax.get_yscale(), "linear")

    def test_defaults_to_linear_when_no_hint_and_no_kwarg(self):
        ax = _line_plot().line()
        self.assertEqual(ax.get_yscale(), "linear")

    def test_uses_lablaxis_hint_for_yaxis_label_when_not_explicit(self):
        ax = _line_plot(values_meta={"LABLAXIS": "Foo"}).line(units="nT")
        self.assertEqual(ax.get_ylabel(), "Foo (nT)")

    def test_explicit_yaxis_label_overrides_lablaxis_hint(self):
        ax = _line_plot(values_meta={"LABLAXIS": "Foo"}).line(units="nT", yaxis_label="Bar")
        self.assertEqual(ax.get_ylabel(), "Bar (nT)")

    def test_masks_fillval_by_default(self):
        ax = _line_plot(values_meta={"FILLVAL": -999.0},
                        values_array=np.array([1.0, -999.0, 3.0])).line()
        ydata = ax.get_lines()[0].get_ydata()
        self.assertTrue(np.isnan(ydata[1]))

    def test_mask_fillval_false_disables_masking(self):
        ax = _line_plot(values_meta={"FILLVAL": -999.0},
                        values_array=np.array([1.0, -999.0, 3.0])).line(mask_fillval=False)
        ydata = ax.get_lines()[0].get_ydata()
        self.assertEqual(ydata[1], -999.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_plotting.py tests/test_plotting_hints.py -v`
Expected: `test_logy_true_log_scales_the_axis` and `test_logy_false_keeps_linear_axis` FAIL with `TypeError: line() got an unexpected keyword argument 'logy'`. All of `LineHints` FAILs the same way once it reaches `.line()` (no `logy`/`mask_fillval` support yet), and the label/mask tests fail their assertions (raw name / un-masked value).

- [ ] **Step 3: Write the implementation**

In `speasy/plotting/mpl_backend/__init__.py`, replace lines 19-29:

```python
    def line(self, x, y, ax=None, labels=None, units=None, xaxis_label=None, yaxis_label=None, logy=False, *args,
             **kwargs):
        ax = self._get_ax(ax)
        ax.tick_params(axis='x', labelrotation=45)
        ax.plot(x, y, label=labels, *args, **kwargs)
        if labels is not None:
            ax.legend()
        if units is not None and yaxis_label is not None:
            ax.set_ylabel(f"{yaxis_label} ({units})")
        if xaxis_label is not None:
            ax.set_xlabel(f"{xaxis_label}")
        if logy:
            ax.semilogy()
        return ax
```

In `speasy/plotting/__init__.py`, add the import (after the existing imports, e.g. after line 4's `from ..core.data_containers import ...`):

```python
from .istp_hints import is_log_scale, label_from_meta, mask_fill_values
```

Replace `Plot.line()` (lines 45-54):

```python
    def line(self, *args, backend=None, **kwargs):
        units = kwargs.pop("units", None) or self.values.unit
        labels = kwargs.pop("labels", None) or self.columns_names
        xaxis_label = kwargs.pop("xaxis_label", None) or self.axes[0].name
        yaxis_label = kwargs.pop("yaxis_label", None) or label_from_meta(self.values.meta) or self.values.name
        logy = kwargs.pop("logy", None)
        if logy is None:
            logy = is_log_scale(self.values.meta)
        if logy is None:
            logy = False
        mask_fillval = kwargs.pop("mask_fillval", True)
        y = mask_fill_values(self.values.values, self.values.meta) if mask_fillval else self.values.values
        return self._get_backend(backend).line(x=self.axes[0].values, y=y, labels=labels,
                                               units=units,
                                               xaxis_label=xaxis_label,
                                               yaxis_label=yaxis_label,
                                               logy=logy, *args,
                                               **kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_plotting.py tests/test_plotting_hints.py -v`
Expected: PASS (all `MplBackendLine`/`MplBackendColormap` tests in `test_plotting.py`, all `LineHints` tests in `test_plotting_hints.py`)

- [ ] **Step 5: Commit**

```bash
git add speasy/plotting/mpl_backend/__init__.py speasy/plotting/__init__.py tests/test_plotting.py tests/test_plotting_hints.py
git commit -m "feat: honor ISTP SCALETYP/LABLAXIS/FILLVAL hints in line plots"
```

---

### Task 3: Wire hints into colormap (spectrogram) plots

**Files:**
- Modify: `speasy/plotting/__init__.py:56-70` (`Plot.colormap`)
- Modify: `tests/test_plotting_hints.py` (add colormap section)

**Interfaces:**
- Consumes: same four functions from `speasy/plotting/istp_hints.py` as Task 2, already imported in `speasy/plotting/__init__.py`.
- Produces: `speasy.plotting.Plot.colormap()` accepting `logy=None, logz=None, mask_fillval=True` with the confirmed precedence. No `mpl_backend.Plot.colormap()` signature change needed — it already accepts concrete `logy`/`logz` booleans and is always called with a resolved (non-`None`) value from the wrapper.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_plotting_hints.py` (new imports at top: `from matplotlib.colors import LogNorm`; new class at the end, before the `if __name__ == "__main__":` block):

```python
def _colormap_plot(values_meta=None, y_axis_meta=None, values_array=None):
    y = np.array([10.0, 20.0])
    values = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]) if values_array is None else values_array
    return Plot(
        axes=[
            VariableTimeAxis(values=_TIME),
            VariableAxis(values=y, meta=y_axis_meta or {}),
        ],
        values=DataContainer(values=values, meta=values_meta or {}, name="raw_name"),
        columns_names=["value"],
    )


class ColormapHints(unittest.TestCase):
    def setUp(self):
        self.addCleanup(plt.close, "all")

    def test_uses_scaletyp_hint_for_logz_when_not_explicit(self):
        ax = _colormap_plot(values_meta={"SCALETYP": "linear"}).colormap()
        mesh = ax.collections[0]
        self.assertNotIsInstance(mesh.norm, LogNorm)

    def test_explicit_logz_overrides_scaletyp_hint(self):
        ax = _colormap_plot(values_meta={"SCALETYP": "log"}).colormap(logz=False)
        mesh = ax.collections[0]
        self.assertNotIsInstance(mesh.norm, LogNorm)

    def test_defaults_to_log_when_no_hint_and_no_kwarg(self):
        ax = _colormap_plot().colormap()
        mesh = ax.collections[0]
        self.assertIsInstance(mesh.norm, LogNorm)

    def test_uses_scaletyp_hint_for_logy_when_not_explicit(self):
        ax = _colormap_plot(y_axis_meta={"SCALETYP": "linear"}).colormap(logz=False)
        self.assertEqual(ax.get_yscale(), "linear")

    def test_masks_fillval_in_z_by_default(self):
        values = np.array([[1.0, 2.0], [3.0, -999.0], [5.0, 6.0]])
        ax = _colormap_plot(values_meta={"FILLVAL": -999.0}, values_array=values).colormap(logz=False)
        mesh = ax.collections[0]
        self.assertTrue(np.isnan(mesh.get_array()).any())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_plotting_hints.py -v`
Expected: `ColormapHints` tests FAIL — `test_defaults_to_log_when_no_hint_and_no_kwarg` currently passes already (hardcoded `logy=True, logz=True`), but `test_uses_scaletyp_hint_for_logz_when_not_explicit`, `test_uses_scaletyp_hint_for_logy_when_not_explicit` and `test_masks_fillval_in_z_by_default` FAIL since the hint isn't wired in yet.

- [ ] **Step 3: Write the implementation**

Replace `Plot.colormap()` in `speasy/plotting/__init__.py` (lines 56-70):

```python
    def colormap(self, *args, logy=None, logz=None, backend=None, **kwargs):
        x_axis_label = kwargs.pop("xaxis_label", None) or self.axes[0].name
        yaxis_units = kwargs.pop("yaxis_units", None) or self.axes[1].unit
        yaxis_label = kwargs.pop("yaxis_label", None) or label_from_meta(self.axes[1].meta) or self.axes[1].name
        zaxis_units = kwargs.pop("zaxis_units", None) or self.values.unit
        zaxis_label = kwargs.pop("zaxis_label", None) or label_from_meta(self.values.meta) or self.values.name
        if logy is None:
            logy = is_log_scale(self.axes[1].meta)
        if logy is None:
            logy = True
        if logz is None:
            logz = is_log_scale(self.values.meta)
        if logz is None:
            logz = True
        mask_fillval = kwargs.pop("mask_fillval", True)
        z = mask_fill_values(self.values.values, self.values.meta) if mask_fillval else self.values.values
        return self._get_backend(backend).colormap(x=self.axes[0].values, y=self.axes[1].values.T,
                                                   z=z.T,
                                                   xaxis_label=x_axis_label,
                                                   yaxis_label=yaxis_label,
                                                   yaxis_units=yaxis_units,
                                                   zaxis_label=zaxis_label,
                                                   zaxis_units=zaxis_units,
                                                   logy=logy,
                                                   logz=logz, *args, **kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_plotting_hints.py tests/test_plotting.py tests/test_istp_hints.py -v`
Expected: PASS (all tests across all three files)

- [ ] **Step 5: Commit**

```bash
git add speasy/plotting/__init__.py tests/test_plotting_hints.py
git commit -m "feat: honor ISTP SCALETYP/LABLAXIS/FILLVAL hints in colormap plots"
```

---

### Task 4: Docs — document the new defaults, refresh the affected image

**Files:**
- Modify: `docs/user/plotting.rst`
- Modify: `docs/user/images/plotting_spectrogram.png` (regenerated; its colorbar label changes from the raw CDF variable name `flux__C1_CP_CIS_HIA_HS_1D_PEF` to the ISTP `LABLAXIS` value, `"Particle Energy Flux"`)

**Interfaces:**
- None — this task is documentation-only, no code interfaces produced or consumed.

- [ ] **Step 1: Confirm which existing doc images actually change**

Every code sample in `docs/user/plotting.rst` up through "Customizing the plot" and the new overlay section passes explicit `yaxis_label=`/`units=` kwargs, so those three images (`plotting_line.png`, `plotting_custom.png`, `plotting_overlay.png`) are unaffected — explicit kwargs always win over the new hints. Only the Spectrograms section's `flux.plot(cmap="jet")` call passes no label kwargs, so its colorbar label changes. Verify with:

```bash
uv run python - <<'EOF'
import speasy as spz
csa = spz.inventories.tree.csa.Cluster.Cluster_1.CIS_HIA1.C1_CP_CIS_HIA_HS_1D_PEF
flux = spz.get_data(csa.flux__C1_CP_CIS_HIA_HS_1D_PEF, "2006-11-01", "2006-11-02")
print(flux.meta.get("LABLAXIS"), flux.values.name if hasattr(flux, "values") else None)
EOF
```

Expected output: `Particle Energy Flux` (confirming the label will change from the raw variable name).

- [ ] **Step 2: Update the doc text**

In `docs/user/plotting.rst`, after the "Spectrograms" section's existing paragraph (the one ending "...are passed through to matplotlib.") and before its code block, add:

```rst
When the source metadata provides them, ``.plot()`` also picks up a few ISTP attributes
automatically: ``SCALETYP`` sets the default log/linear scale (still overridable with
``logy``/``logz``), ``FILLVAL`` entries are masked to NaN before plotting (disable with
``mask_fillval=False``), and ``LABLAXIS`` is preferred over the raw CDF variable name for
axis and colorbar labels when you don't pass one explicitly.
```

- [ ] **Step 3: Regenerate the spectrogram image**

```bash
source .venv/bin/activate && python - <<'EOF'
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import speasy as spz

csa = spz.inventories.tree.csa.Cluster.Cluster_1.CIS_HIA1.C1_CP_CIS_HIA_HS_1D_PEF
flux = spz.get_data(csa.flux__C1_CP_CIS_HIA_HS_1D_PEF, "2006-11-01", "2006-11-02")
flux.plot(cmap="jet")
plt.savefig("docs/user/images/plotting_spectrogram.png", dpi=100)
EOF
```

- [ ] **Step 4: Visually confirm the regenerated image**

Read `docs/user/images/plotting_spectrogram.png` and confirm the colorbar label now reads "Particle Energy Flux (keV cm^-2 s^-1 sr^-1 keV^-1)" instead of the raw variable name, and that the plot otherwise looks the same as before (same data, same colors).

- [ ] **Step 5: Build the docs and check for warnings**

```bash
make doctest 2>&1 | tail -30
```

Expected: no new errors; doctest count unchanged (this page has no `>>>` doctests, only illustrative `code-block:: python` samples).

- [ ] **Step 6: Commit**

```bash
git add docs/user/plotting.rst docs/user/images/plotting_spectrogram.png
git commit -m "docs: document ISTP metadata-driven plot defaults"
```

---

## Self-Review

- **Spec coverage:** `SCALETYP` → Task 2 (line) + Task 3 (colormap). `FILLVAL` → Task 1 (masking function) + Tasks 2/3 (wiring, with `mask_fillval` opt-out). `LABLAXIS` → Task 1 (extraction) + Tasks 2/3 (wiring). Priority order (kwarg > hint > hardcoded default) → enforced via `is None` checks in every wiring site, tested explicitly in Tasks 2 and 3. Docs → Task 4.
- **Placeholder scan:** none — every step has complete, runnable code.
- **Type/signature consistency:** `scale_type_from_meta`, `is_log_scale`, `label_from_meta`, `mask_fill_values` are defined once in Task 1 and imported with the same names/signatures in Task 2's `speasy/plotting/__init__.py` edit; Task 3 reuses the same import line (already added in Task 2, not re-added). `mpl_backend.Plot.line()`'s new `logy` parameter (Task 2) matches the `logy=logy` keyword used when `speasy.plotting.Plot.line()` calls it. `mpl_backend.Plot.colormap()`'s existing `logy`/`logz` parameters are untouched and already accept the concrete booleans `speasy.plotting.Plot.colormap()` resolves in Task 3.
