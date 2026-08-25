# Upgrade-Path CI Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CI job that installs curated old Speasy releases, fetches real data (populating the cache), upgrades in place, and fetches more — some of it overlapping already-cached fragments — to catch upgrade-path regressions that no existing test covers.

**Architecture:** Two small, independently unit-tested Python scripts under `.github/scripts/` (a fetch script run once per version step, and a driver that installs each version in turn and calls the fetch script), wired into a new GitHub Actions workflow that runs both a `sequential` and a `direct-jump` scenario across all three OSes.

**Tech Stack:** Python 3.10 (stdlib `argparse`/`subprocess`/`json` only — no new dependencies), pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-upgrade-path-ci-test-design.md`

## Global Constraints

- Python pinned at 3.10 for the whole upgrade-path job (oldest version every curated release, 1.5.2 through `main`, supports).
- Curated version list is exactly `1.5.2`, `1.7.1`, `main` (see spec's "Version list" section for why).
- Job is non-blocking: `continue-on-error: true` at the job level. Never wire this as a required check.
- Reuse the existing `secrets.SPEASY_AMDA_USERNAME` / `secrets.SPEASY_AMDA_PASSWORD` (already defined for `tests.yml`) — do not add new secrets.
- The fetch script must use only the long-stable `spz.get_data(product, start, stop)` / `spz.list_providers()` surface — no APIs newer than what 1.5.2 shipped.
- No hardcoded "provider X added in version Y" table — provider availability is always checked at runtime via `spz.list_providers()`.

---

### Task 1: Fetch script (`upgrade_path_fetch.py`)

**Files:**
- Create: `.github/scripts/upgrade_path_fetch.py`
- Test: `tests/test_upgrade_path_scripts.py`

**Interfaces:**
- Produces: `fetch_amda(get_data, step: int, state_file: Path) -> None` — raises `AssertionError` on empty data or on a non-growing result; on success writes `{"amda_imf_length": len(var)}` as JSON to `state_file`.
- Produces: `fetch_single_shot(get_data, product: str, start: str, stop: str) -> None` — raises `AssertionError` if the result is `None` or empty.
- Produces: `SINGLE_SHOT_PRODUCTS: dict[str, tuple[str, str, str]]` — `{provider_name: (product, start, stop)}`, verified-working products for `cda`, `ssc`, `cdpp3dview`.
- Produces: `run(get_data, list_providers, step: int, state_file: Path) -> None` — calls `fetch_amda`, then `fetch_single_shot` for every provider in `SINGLE_SHOT_PRODUCTS` that `list_providers()` reports as available (skips the rest with a printed line).
- Produces: `main(argv=None) -> int` — CLI entry point; imports `speasy` itself (not injected) and calls `run(spz.get_data, spz.list_providers, ...)`.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_upgrade_path_scripts.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Unit tests for the upgrade-path CI job's helper scripts (.github/scripts/).
These scripts aren't part of the speasy package, so they're imported directly
off disk by path rather than as a normal package import."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "scripts"


def _load(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


upgrade_path_fetch = _load("upgrade_path_fetch", "upgrade_path_fetch.py")


class FakeVar:
    def __init__(self, length):
        self._length = length

    def __len__(self):
        return self._length


class FetchAmda(unittest.TestCase):
    def setUp(self):
        self.state_file = Path("/tmp/upgrade_path_state_test.json")
        self.addCleanup(self.state_file.unlink, missing_ok=True)

    def test_first_step_with_no_prior_state_succeeds_and_writes_state(self):
        get_data = mock.Mock(return_value=FakeVar(5400))

        upgrade_path_fetch.fetch_amda(get_data, step=0, state_file=self.state_file)

        self.assertEqual(json.loads(self.state_file.read_text()), {"amda_imf_length": 5400})

    def test_raises_when_result_is_empty(self):
        get_data = mock.Mock(return_value=FakeVar(0))

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.fetch_amda(get_data, step=0, state_file=self.state_file)

    def test_raises_when_result_is_none(self):
        get_data = mock.Mock(return_value=None)

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.fetch_amda(get_data, step=0, state_file=self.state_file)

    def test_growth_check_passes_when_length_increases(self):
        self.state_file.write_text(json.dumps({"amda_imf_length": 5400}))
        get_data = mock.Mock(return_value=FakeVar(8100))

        upgrade_path_fetch.fetch_amda(get_data, step=1, state_file=self.state_file)

        self.assertEqual(json.loads(self.state_file.read_text()), {"amda_imf_length": 8100})

    def test_growth_check_fails_when_length_does_not_increase(self):
        """A growing requested window that doesn't return more data means the
        merge of an older version's cached fragments with newly fetched ones
        likely silently dropped something -- this is the whole point of the
        job, so it must be a hard failure, not a warning."""
        self.state_file.write_text(json.dumps({"amda_imf_length": 8100}))
        get_data = mock.Mock(return_value=FakeVar(8100))

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.fetch_amda(get_data, step=2, state_file=self.state_file)


class FetchSingleShot(unittest.TestCase):
    def test_succeeds_on_non_empty_result(self):
        get_data = mock.Mock(return_value=FakeVar(30))

        upgrade_path_fetch.fetch_single_shot(get_data, "ssc/moon", "2006-01-08T01:00:00",
                                             "2006-01-08T01:30:00")

        get_data.assert_called_once_with("ssc/moon", "2006-01-08T01:00:00", "2006-01-08T01:30:00")

    def test_raises_on_empty_result(self):
        get_data = mock.Mock(return_value=FakeVar(0))

        with self.assertRaises(AssertionError):
            upgrade_path_fetch.fetch_single_shot(get_data, "ssc/moon", "x", "y")


class Run(unittest.TestCase):
    def setUp(self):
        self.state_file = Path("/tmp/upgrade_path_state_run_test.json")
        self.addCleanup(self.state_file.unlink, missing_ok=True)

    def test_skips_providers_not_reported_by_list_providers(self):
        get_data = mock.Mock(return_value=FakeVar(10))
        list_providers = mock.Mock(return_value={"amda", "cda"})  # no ssc, no cdpp3dview

        upgrade_path_fetch.run(get_data, list_providers, step=0, state_file=self.state_file)

        called_products = {call.args[0] for call in get_data.call_args_list}
        self.assertIn("amda/imf", called_products)
        self.assertIn(upgrade_path_fetch.SINGLE_SHOT_PRODUCTS["cda"][0], called_products)
        self.assertNotIn(upgrade_path_fetch.SINGLE_SHOT_PRODUCTS["ssc"][0], called_products)
        self.assertNotIn(upgrade_path_fetch.SINGLE_SHOT_PRODUCTS["cdpp3dview"][0], called_products)

    def test_calls_every_configured_product_when_all_providers_available(self):
        get_data = mock.Mock(return_value=FakeVar(10))
        list_providers = mock.Mock(return_value={"amda", "cda", "ssc", "cdpp3dview"})

        upgrade_path_fetch.run(get_data, list_providers, step=0, state_file=self.state_file)

        called_products = {call.args[0] for call in get_data.call_args_list}
        expected = {"amda/imf"} | {p for p, _, _ in upgrade_path_fetch.SINGLE_SHOT_PRODUCTS.values()}
        self.assertEqual(called_products, expected)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_upgrade_path_scripts.py -v`
Expected: collection error / `FileNotFoundError` — `.github/scripts/upgrade_path_fetch.py` doesn't exist yet.

- [ ] **Step 3: Write the implementation**

Create `.github/scripts/upgrade_path_fetch.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fetch a few small, known-good products through whatever Speasy version is
currently installed. Run once per version step (see upgrade_path_driver.py)
within one persistent environment: AMDA's requested window grows with --step,
so a later step necessarily reuses at least one cache fragment written by an
older Speasy version and merges it with a freshly-fetched one written by the
current version -- the actual thing this CI job exists to catch.

Long-stable API only (spz.get_data / spz.list_providers, both present back to
speasy 1.5.2) so this one script runs unmodified across the whole version
range under test.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

AMDA_ANCHOR = "2016-06-02"
AMDA_FRAGMENT_DAYS = 1

# provider_name -> (product, start, stop). Verified live against the real
# services before being written here -- not guesses. CSA is deliberately
# excluded: no verified small product path was available when this was
# written (its inventory tree structure didn't match the obvious guess), see
# the design spec's "Open follow-ups".
SINGLE_SHOT_PRODUCTS = {
    "cda": ("cda/WI_PLSP_3DP/MOM.P.MAGF", "2018-01-01", "2018-01-02"),
    "ssc": ("ssc/moon", "2006-01-08T01:00:00", "2006-01-08T01:30:00"),
    "cdpp3dview": ("cdpp3dview/GEOTAIL", "1992-07-30T01:00:00", "1992-07-30T02:00:00"),
}


def _amda_stop_for_step(step: int) -> str:
    anchor = datetime.strptime(AMDA_ANCHOR, "%Y-%m-%d")
    stop = anchor + timedelta(days=(step + 2) * AMDA_FRAGMENT_DAYS)
    return stop.strftime("%Y-%m-%d")


def fetch_amda(get_data, step: int, state_file: Path) -> None:
    stop = _amda_stop_for_step(step)
    var = get_data("amda/imf", AMDA_ANCHOR, stop)
    if var is None or len(var) == 0:
        raise AssertionError(f"amda/imf returned no data for step {step} ([{AMDA_ANCHOR}, {stop}))")

    previous_length = None
    if state_file.exists():
        previous_length = json.loads(state_file.read_text()).get("amda_imf_length")

    if previous_length is not None and len(var) <= previous_length:
        raise AssertionError(
            f"amda/imf: requested window grew at step {step} but the returned length did not "
            f"({len(var)} <= {previous_length}) -- merging cache fragments written by an older "
            f"speasy version with freshly-fetched ones likely failed"
        )

    state_file.write_text(json.dumps({"amda_imf_length": len(var)}))
    print(f"amda/imf: {len(var)} samples for [{AMDA_ANCHOR}, {stop})"
          + (f" (previous: {previous_length})" if previous_length is not None else ""))


def fetch_single_shot(get_data, product: str, start: str, stop: str) -> None:
    var = get_data(product, start, stop)
    if var is None or len(var) == 0:
        raise AssertionError(f"{product} returned no data for [{start}, {stop})")
    print(f"{product}: {len(var)} samples")


def run(get_data, list_providers, step: int, state_file: Path) -> None:
    available = set(list_providers())
    print(f"available providers: {sorted(available)}")

    fetch_amda(get_data, step, state_file)

    for provider, (product, start, stop) in SINGLE_SHOT_PRODUCTS.items():
        if provider not in available:
            print(f"skip {product}: {provider!r} not available in this speasy version")
            continue
        fetch_single_shot(get_data, product, start, stop)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--state-file", type=Path, default=Path("upgrade_path_state.json"))
    args = parser.parse_args(argv)

    import speasy as spz

    print(f"speasy {spz.__version__}, step {args.step}")
    run(spz.get_data, spz.list_providers, args.step, args.state_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_upgrade_path_scripts.py -v`
Expected: all `FetchAmda`, `FetchSingleShot`, `Run` tests PASS.

- [ ] **Step 5: Lint**

Run: `uv run --with flake8 flake8 .github/scripts/upgrade_path_fetch.py tests/test_upgrade_path_scripts.py --count --select=E9,F63,F7,F82 --show-source --statistics`
Expected: `0`

- [ ] **Step 6: Commit**

```bash
git add .github/scripts/upgrade_path_fetch.py tests/test_upgrade_path_scripts.py
git commit -m "$(cat <<'EOF'
ci: add the upgrade-path fetch script

One script, unchanged across every Speasy version under test, that
fetches a few small known-good products and asserts the result --
including a length-growth check on AMDA/imf that specifically catches
a broken merge of cache fragments written by an older Speasy version
with freshly-fetched ones.
EOF
)"
```

---

### Task 2: Driver script (`upgrade_path_driver.py`)

**Files:**
- Create: `.github/scripts/upgrade_path_driver.py`
- Test: `tests/test_upgrade_path_scripts.py` (extend from Task 1)

**Interfaces:**
- Consumes: nothing directly from Task 1's module (it invokes `upgrade_path_fetch.py` as a subprocess, not an import — this mirrors the real CI use: each step must run under whatever Speasy version was *just installed*, so re-importing an already-imported `speasy` module in the same process wouldn't work).
- Produces: `install_target(version: str, repo_root: Path) -> str` — `str(repo_root)` for `"main"`, else `f"speasy=={version}"`.
- Produces: `run_steps(versions: list[str], repo_root: Path, fetch_script: Path, state_file: str, installer, runner) -> None` — for each `(step, version)` in `enumerate(versions)`, calls `installer(version, repo_root, runner)` then `runner([sys.executable, str(fetch_script), "--step", str(step), "--state-file", state_file], check=True)`.
- Produces: `main(argv=None) -> int` — CLI entry point (`--versions "1.5.2,1.7.1,main"` comma-separated, `--state-file`), wires `install` (the real `subprocess.run`-backed installer) and `subprocess.run` into `run_steps`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_upgrade_path_scripts.py`:

```python
upgrade_path_driver = _load("upgrade_path_driver", "upgrade_path_driver.py")


class InstallTarget(unittest.TestCase):
    def test_main_uses_the_checked_out_repo_root(self):
        repo_root = Path("/repo")

        self.assertEqual(upgrade_path_driver.install_target("main", repo_root), "/repo")

    def test_pinned_version_uses_a_pypi_spec(self):
        repo_root = Path("/repo")

        self.assertEqual(upgrade_path_driver.install_target("1.5.2", repo_root), "speasy==1.5.2")


class RunSteps(unittest.TestCase):
    def test_installs_and_fetches_each_version_in_order(self):
        installer_calls = []
        runner_calls = []

        def fake_installer(version, repo_root, runner):
            installer_calls.append(version)

        def fake_runner(cmd, check):
            runner_calls.append(cmd)

        upgrade_path_driver.run_steps(
            versions=["1.5.2", "1.7.1", "main"],
            repo_root=Path("/repo"),
            fetch_script=Path("/repo/.github/scripts/upgrade_path_fetch.py"),
            state_file="state.json",
            installer=fake_installer,
            runner=fake_runner,
        )

        self.assertEqual(installer_calls, ["1.5.2", "1.7.1", "main"])
        # cmd shape: [sys.executable, fetch_script, "--step", step, "--state-file", state_file]
        self.assertEqual([call[2] for call in runner_calls], ["--step", "--step", "--step"])
        self.assertEqual([call[3] for call in runner_calls], ["0", "1", "2"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_upgrade_path_scripts.py -v -k "InstallTarget or RunSteps"`
Expected: `FileNotFoundError` — `.github/scripts/upgrade_path_driver.py` doesn't exist yet.

- [ ] **Step 3: Write the implementation**

Create `.github/scripts/upgrade_path_driver.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Drive the upgrade-path CI job for one scenario: install each version in
the given order (from PyPI, or from the checked-out working tree for
"main"), running upgrade_path_fetch.py after each install. All steps share
the same interpreter/site-packages and the same current directory across the
whole run, so the cache/index/config Speasy writes at one step is exactly
what the next step's (newer) Speasy sees -- that persistence, entirely via
the OS filesystem, is what makes this an upgrade-path test rather than N
independent single-version smoke tests.
"""
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FETCH_SCRIPT = SCRIPT_DIR / "upgrade_path_fetch.py"
REPO_ROOT = SCRIPT_DIR.parent.parent


def install_target(version: str, repo_root: Path) -> str:
    if version == "main":
        return str(repo_root)
    return f"speasy=={version}"


def install(version: str, repo_root: Path, runner) -> None:
    runner([sys.executable, "-m", "pip", "install", "--upgrade", "--quiet",
            install_target(version, repo_root)], check=True)


def run_steps(versions, repo_root: Path, fetch_script: Path, state_file: str,
              installer=install, runner=subprocess.run) -> None:
    for step, version in enumerate(versions):
        print(f"::group::step {step}: speasy {version}")
        installer(version, repo_root, runner)
        runner([sys.executable, str(fetch_script), "--step", str(step),
                "--state-file", state_file], check=True)
        print("::endgroup::")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", required=True,
                        help="comma-separated version list, e.g. 1.5.2,1.7.1,main")
    parser.add_argument("--state-file", default="upgrade_path_state.json")
    args = parser.parse_args(argv)

    run_steps(args.versions.split(","), REPO_ROOT, FETCH_SCRIPT, args.state_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_upgrade_path_scripts.py -v`
Expected: every test in the file PASSES (Task 1's tests plus this task's).

- [ ] **Step 5: Lint**

Run: `uv run --with flake8 flake8 .github/scripts/upgrade_path_driver.py tests/test_upgrade_path_scripts.py --count --select=E9,F63,F7,F82 --show-source --statistics`
Expected: `0`

- [ ] **Step 6: Commit**

```bash
git add .github/scripts/upgrade_path_driver.py tests/test_upgrade_path_scripts.py
git commit -m "$(cat <<'EOF'
ci: add the upgrade-path driver script

Installs each curated version in turn (PyPI pin, or the checked-out
working tree for "main") and runs upgrade_path_fetch.py after each --
one process, one persistent environment, so later steps see exactly
what an earlier (older) Speasy version wrote to disk.
EOF
)"
```

---

### Task 3: Workflow (`upgrade_path.yml`)

**Files:**
- Create: `.github/workflows/upgrade_path.yml`

**Interfaces:**
- Consumes: `upgrade_path_driver.py --versions <comma-separated> --state-file <path>` (Task 2's CLI).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/upgrade_path.yml`:

```yaml
name: Upgrade path

on:
  pull_request:
  push:
  schedule:
    # Runs at 05:00 UTC on Mondays and Thursdays
    - cron: "0 5 * * 1,4"

jobs:
  upgrade-path:
    # Old-version installs and extra real network calls make this job more
    # failure-prone than tests.yml; it must never block a merge on its own.
    continue-on-error: true
    runs-on: ${{ matrix.os }}
    timeout-minutes: 30
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        scenario: [sequential, direct-jump]
        # `scenario` must be a real matrix axis (not just introduced via
        # `include`, below) so it cross-products against `os` into 6 jobs.
        # An `include` entry with no `os` key merges into *every* existing
        # os combination instead of creating its own -- with two such
        # entries the second would silently overwrite the first's added
        # keys on the same 3 combos, collapsing "sequential" out entirely.
        # Matching on `scenario` (an existing axis value) avoids that.
        include:
          # 1.7.1 is the newest actual PyPI release; the sciqlop-cache
          # backend migration only exists on unreleased main (1.8.0-dev) --
          # see the design spec for why this list is exactly these three.
          - scenario: sequential
            versions: "1.5.2,1.7.1,main"
          - scenario: direct-jump
            versions: "1.5.2,main"

    steps:
    - uses: actions/checkout@v7
      with:
        # main's version is derived from git describe, so tags must be present
        fetch-depth: 0
    - name: Set up Python 3.10
      uses: actions/setup-python@v7
      with:
        python-version: "3.10"
    - name: Give Windows the same TCP connect patience as Linux
      if: runner.os == 'Windows'
      shell: pwsh
      # See tests.yml for the measurements behind this -- Windows abandons an
      # unanswered TCP connect far sooner than its own or Speasy's timeouts
      # expect, which breaks real network calls to AMDA/CDA/SSC here too.
      run: |
        foreach ($s in Get-NetTCPSetting | Where-Object { $_.SettingName -ne 'Automatic' }) {
          Set-NetTCPSetting -SettingName $s.SettingName -MaxSynRetransmissions 6
        }
    - name: Walk the upgrade path
      env:
        SPEASY_AMDA_USERNAME: ${{ secrets.SPEASY_AMDA_USERNAME }}
        SPEASY_AMDA_PASSWORD: ${{ secrets.SPEASY_AMDA_PASSWORD }}
        SPEASY_AMDA_MAX_CHUNK_SIZE_DAYS: "1"
      run: python .github/scripts/upgrade_path_driver.py --versions "${{ matrix.versions }}"
```

- [ ] **Step 2: Validate the YAML parses**

Run: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/upgrade_path.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Validate the referenced secrets/env vars match `tests.yml`'s existing names**

Run: `grep -n "SPEASY_AMDA_USERNAME\|SPEASY_AMDA_PASSWORD" .github/workflows/tests.yml .github/workflows/upgrade_path.yml`
Expected: both files reference the identical secret names (`SPEASY_AMDA_USERNAME`, `SPEASY_AMDA_PASSWORD`).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/upgrade_path.yml
git commit -m "$(cat <<'EOF'
ci: add the upgrade-path workflow

Runs the sequential (1.5.2 -> 1.7.1 -> main) and direct-jump
(1.5.2 -> main) scenarios across all three OSes, on every PR/push and
twice a week. Non-blocking (continue-on-error) since old-version
installs and extra real network calls make it more failure-prone than
the rest of CI.
EOF
)"
```

---

### Task 4: End-to-end local smoke check

**Files:** none created or modified — this task only runs what Tasks 1-3 produced, against the currently-installed (`main`) Speasy, to catch a trivial bug (a typo'd product path, a wrong CLI flag) before relying on a full CI run to surface it.

**Interfaces:** none.

- [ ] **Step 1: Run the fetch script directly against the dev environment**

```bash
uv run python .github/scripts/upgrade_path_fetch.py --step 0 --state-file /tmp/upgrade_path_smoke.json
```

Expected: exits 0; prints `speasy <version>, step 0`, the available-providers line, an `amda/imf: N samples for [2016-06-02, 2016-06-04)` line, and one line per available single-shot product (`cda/...`, `ssc/moon`, `cdpp3dview/GEOTAIL` — all four expected present, since this is `main`).

- [ ] **Step 2: Run it again with a later step to confirm the growth check**

```bash
uv run python .github/scripts/upgrade_path_fetch.py --step 1 --state-file /tmp/upgrade_path_smoke.json
```

Expected: exits 0; the `amda/imf` line shows a larger sample count than step 0's, with `(previous: <step-0-count>)` printed.

- [ ] **Step 3: Clean up the smoke-test state file**

```bash
rm -f /tmp/upgrade_path_smoke.json
```

- [ ] **Step 4: Run the full project test suite once more to confirm nothing else broke**

Run: `uv run pytest tests/test_upgrade_path_scripts.py -v`
Expected: all tests still PASS (no code changes in this task, this is a final confidence check before calling the plan done).

No commit for this task — it produced no file changes.
