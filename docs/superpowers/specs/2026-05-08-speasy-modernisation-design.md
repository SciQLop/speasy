# Speasy Modernisation Design

**Status**: approved 2026-05-08
**Author**: Alexis Jeandet (with Claude)
**Scope**: tooling modernisation (UV, ruff, basedpyright, hatchling) and test
infrastructure overhaul (three-tier strategy with cassette-based mocks). Shipped
as a sequence of small, independently reviewable PRs.

---

## 1. Goals & non-goals

### Goals

1. **Catch upstream API/data changes.** When AMDA, CDA, CSA, SSC, or
   CDPP3DView change a response shape, header, or schema, Speasy's CI must
   notice — not the next user who runs `spz.get_data`.
2. **Catch regressions in PRs.** Every push gets fast (minutes, not 30+ min),
   deterministic, network-free feedback that exercises Speasy's own logic.
3. **Confirm "works out of the box" on every supported platform.** Real
   end-to-end fetches succeed on Linux, macOS, Windows × Python 3.10–3.14, on
   a regular schedule.
4. **Modern, strict-but-not-pedantic tooling.** UV-driven workflow, ruff for
   lint+format, basedpyright for typing, codespell for typos. Mirror
   AstraLint's stack with adjustments where Speasy differs.
5. **Single source of truth for dependencies and version.** Drop
   `requirements*.txt` duplication and the 5-file `bumpversion` sync.
6. **Ship as small reviewable PRs.** No PR should require a reviewer to hold
   more than one concern in their head at once.

### Non-goals (deferred to other efforts)

- Refactoring `SpeasyVariable` (P1 backlog item).
- Fixing import-time hang when AMDA is unreachable (P0 backlog, GH #236).
- Adding new providers (HAPI, CLWeb, SuperMAG, etc.).
- Offline mode (GH #237).
- Migrating from `diskcache` to `sciqlop-cache` (separate plan exists).
- Plugin architecture for providers (GH #273).

---

## 2. Three-tier test architecture

The current test suite (~35 files) mostly hits real servers. That single tier
tries to satisfy three different goals at once and fails at all of them:
slow per-PR feedback, brittle to upstream flakiness, no clean signal when
the upstream actually breaks.

We split it into three tiers, each tuned for one goal.

| Tier      | Marker                       | Network | OS×Py matrix | Trigger                              | Goal                          |
|-----------|------------------------------|---------|--------------|--------------------------------------|-------------------------------|
| Unit      | `@pytest.mark.unit` (default)| mocked  | full         | every push & PR                      | regressions (Goal 2)          |
| Contract  | `@pytest.mark.contract`      | real    | one runner   | scheduled (daily) + manual           | upstream API drift (Goal 1)   |
| E2E smoke | `@pytest.mark.e2e`           | real    | full         | scheduled (weekly) + workflow_dispatch | platform install/run (Goal 3) |

**Default `pytest`** (and per-PR CI) runs only the unit tier. Marker
configuration in `pyproject.toml` makes `pytest -m unit` the default via
`addopts`, with explicit `-m contract` / `-m e2e` for the other tiers.

**Unit tier** is populated by a mix:

- **Cassettes** via `pytest-recording` (vcrpy-based) for the bulk migration
  of existing tests. Recorded once from real servers, replayed from disk.
  Stored under `tests/cassettes/<test_module>/<test_name>.yaml`.
- **Hand-written `pytest-httpserver` fixtures** for cases needing surgical
  control: specific error responses, edge cases, malformed payloads,
  retries, redirects.

**Contract tier** is small and lightweight:

- One probe per provider with a known-stable product and time range.
- Asserts response *shape* (variable names, dimensions, dtype categories) —
  not exact values, which legitimately drift.
- Acts as the watchdog for cassette drift: when contract fails, the
  cassettes for that provider need re-recording.

**E2E tier** mirrors a few canonical user workflows:

- `spz.get_data(<famous_product>, <range>)` for each provider.
- Inventory load + tree access.
- Plotting smoke (matplotlib backend, no display).
- ~5–10 tests total, kept deliberately small.

---

## 3. Tooling stack

Mirrors `AstraLint`'s `pyproject.toml` with adjustments for Speasy's
constraints. See AstraLint at `/home/jeandet/Documents/prog/AstraLint/pyproject.toml`
for the canonical source.

### Build & dependencies

- **Build backend**: `hatchling` + `uv-dynamic-versioning` (version derived
  from git tags via PEP 440). Replaces `flit_core`.
- **Dependency management**: `uv` for everything (sync, lock, run).
  - `[project.dependencies]`: runtime deps (unchanged content from current
    pyproject).
  - `[dependency-groups].dev`: dev deps. Replaces `requirements_dev.txt`.
  - `uv.lock` checked into git.
  - `requirements.txt` and `requirements_dev.txt` deleted.
- **`__version__`**:
  ```python
  from importlib.metadata import version, PackageNotFoundError
  try:
      __version__ = version("speasy")
  except PackageNotFoundError:
      __version__ = "0.0.0+dev"
  ```
  Fallback covers `PYTHONPATH=.` / vendored-source users where no
  metadata exists. Normal dev workflow (`uv sync` → editable install) hits
  the metadata path.
- **`bumpversion` deleted**. Replaced with `scripts/release.sh VERSION` that:
  1. Updates `CITATION.cff` `version:` and `date-released:`.
  2. Commits the change.
  3. Creates the `vVERSION` git tag.
  4. Pushes both.
  Hatchling reads the tag at build time; everything else flows from there.

### Lint & format

- **Ruff** with `[tool.ruff.lint] select = ["E", "F", "UP", "B", "I"]`,
  line-length 100. Standard AstraLint ignore set
  (`E501,E402,E731,W191,E111,E114,E117,D206,D300,Q000-Q003,COM812,COM819,ISC002`).
- **Ruff formatter** enabled. Replaces black/autopep8.
- **flake8** removed.
- **codespell** with `ignore-words-list` populated from false positives
  encountered during PR 12.

### Type checking

- **basedpyright** in `standard` mode, `include = ["speasy", "tests"]`.
- AstraLint's noise-reduction overrides applied as the starting point
  (`reportIgnoreCommentWithoutRule = false`,
  `reportUnnecessaryTypeIgnoreComment = false`,
  `reportMissingTypeStubs = false`,
  `reportUnusedCallResult = false`,
  `reportAny = false`,
  `reportExplicitAny = false`,
  `reportImplicitStringConcatenation = false`,
  `reportUnreachable = false`).
- Initially **non-blocking** CI job (PR 13). Becomes **blocking** in PR 15
  after the typing-fix PR (PR 14) clears existing errors.

### Test runner

- `pytest-sugar` for output.
- `pytest-cov` with branch coverage.
- `pytest-recording` for cassettes.
- `pytest-httpserver` for hand-written HTTP fixtures.

### Coverage

- Branch coverage on, source = `["speasy"]`, exclude lines mirroring
  AstraLint's standard set.
- `fail_under` set in PR 16 to `(measured_after_migration − 2%)`. Ratchets
  up over time as new tests land. Never panic-blocks.

### Python floor

- Bumped from `>=3.9` to `>=3.10`. CI matrix already starts at 3.10; the
  declared floor catches up. Unlocks PEP 604 unions and built-in generics
  for the typing-fix PR.

---

## 4. CI workflow shape

Current `tests.yml` is split:

- **`lint.yml`** (every push): ruff check, ruff format --check, codespell,
  basedpyright. Single runner. Fast.
- **`unit.yml`** (every push): full OS×Py matrix, `uv run pytest -m unit`.
  Coverage uploaded from one job (Linux × Python 3.13). Doctests run here
  too.
- **`contract.yml`** (cron daily + workflow_dispatch): one runner (Linux ×
  3.13), `uv run pytest -m contract`. Failure pings the maintainer.
- **`e2e.yml`** (cron weekly + workflow_dispatch): full OS×Py matrix,
  `uv run pytest -m e2e`. The expensive one, kept rare.
- **`pythonpublish.yml`**, **`codeql.yml`**, **`PRs.yml`**,
  **`wasm_tests.yml`**, **`check_for_gha_updates.yml`**: untouched.

All `*_tests`-style workflows use `astral-sh/setup-uv` + `uv sync --group dev`.
The `SPEASY_AMDA_USERNAME`/`SPEASY_AMDA_PASSWORD` secrets remain wired into
`contract.yml` and `e2e.yml`; the unit tier never needs them.

---

## 5. PR sequence (Approach 2)

Each PR is independently mergeable and revertible. PRs 4–9 can land in any
order. PRs 11–15 can land in parallel with later cassette PRs.

### PR 1 — Foundation: Python ≥3.10 + UV + dependency-groups

- Bump `requires-python` to `>=3.10`; drop 3.9 classifier.
- Add `[dependency-groups].dev` with current `requirements_dev.txt` content.
- Generate `uv.lock`, commit.
- Update `tests.yml` to use `astral-sh/setup-uv@v6` + `uv sync --group dev`
  + `uv run pytest`.
- Delete `requirements.txt`, `requirements_dev.txt`, `environment.yml` (if
  unused), `setup.cfg`.
- Update `CLAUDE.md`, `CONTRIBUTING.rst`, `Makefile`, `README.md`,
  `.readthedocs.yaml` to drop `PYTHONPATH=.` pattern in favor of
  `uv sync && uv run pytest`.

### PR 2 — Test markers + CI split

- Register markers `unit`, `contract`, `e2e` in `pyproject.toml`.
- Mark every existing test file. Heuristic for initial labelling:
  - Tests that hit network → `contract` (will be migrated in PR 4–9).
  - Pure-logic tests (e.g. `test_speasy_variable.py`, `test_datetimerange.py`,
    `test_url_utils.py`, `test_filtering.py`, `test_resampling.py`) → `unit`.
  - A small curated set per provider → `e2e`.
- Add `addopts = "-m unit"` default in `pyproject.toml` so `pytest` runs
  unit by default.
- Split `tests.yml` into `unit.yml`, `contract.yml`, `e2e.yml`, `lint.yml`
  (placeholder, populated as later PRs add tools).
- Mechanical marker decoration done via a one-off script committed to
  `devtools/` so reviewer can verify the diff is purely mechanical.

### PR 3 — Mocking infrastructure

- Add `pytest-recording`, `pytest-httpserver`, `pytest-sugar` to dev group.
- Configure `pytest-recording` defaults in `tests/conftest.py`: cassette
  directory, record mode `none` (replay only) by default, `--record-mode`
  CLI flag respected.
- Build proper `tests/conftest.py` (replaces near-empty current one) with:
  - shared fixtures for `SpeasyVariable` factories,
  - HTTP server fixtures (`pytest-httpserver`),
  - a `tmp_speasy_cache` fixture isolating cache state per test,
  - a `disable_proxy` autouse fixture for unit tier.
- No test conversions yet; this PR only adds infrastructure.

### PRs 4–9 — Per-provider cassette migration

One PR per provider. Each PR:

1. Re-runs the provider's existing `contract`-marked tests against real
   servers with `--record-mode=once` to populate cassettes under
   `tests/cassettes/<provider>/`.
2. Adds a `unit`-marked replay version of each test.
3. Keeps the original real-network test under `contract` marker (becomes
   the cassette-drift watchdog probe for that provider).
4. Adds 1–2 hand-written `pytest-httpserver` fixtures for failure paths
   not covered by happy-path cassettes (timeout, 500, malformed payload).

| PR  | Provider         | Test files                                                    |
|-----|------------------|---------------------------------------------------------------|
| 4   | AMDA             | `test_amda.py`, `test_amda_parameter.py`, `test_amda_catalog.py`, `test_amda_timetable.py` |
| 5   | CDA              | `test_cdaweb.py`                                              |
| 6   | CSA              | `test_csa.py`                                                 |
| 7   | SSC              | `test_sscweb.py`                                              |
| 8   | GenericArchive   | `test_direct_archive_downloader.py`, `test_file_access.py`    |
| 9   | CDPP3DView       | `test_cdpp3dview.py`                                          |

Cassette repo-size budget: re-evaluate if `tests/cassettes/` exceeds ~50 MB.
If exceeded, switch that provider's cassettes to `git-lfs` in a follow-up.

### PR 10 — Build backend swap

- Replace `[build-system]` block with hatchling + uv-dynamic-versioning.
- Add `[tool.hatch.version]`, `[tool.uv-dynamic-versioning]`,
  `[tool.hatch.build.targets.wheel]`.
- Set `dynamic = ["version"]` in `[project]`, remove the static `version`.
- Replace hardcoded `__version__` in `speasy/__init__.py` with
  `importlib.metadata` + fallback.
- Replace hardcoded `version = '1.7.1'` in `docs/conf.py:136` with
  `from speasy import __version__ as version`.
- Delete `[tool.bumpversion]` config; delete `VERSION` file.
- Add `scripts/release.sh` with the four-step release flow.
- Verify built artifacts: build wheel + sdist with hatchling, diff
  contents (`unzip -l`, `tar -tzf`) against the last flit-built artifact;
  attach the diff to the PR description.

### PR 11 — Ruff config + autofixes

- Add `[tool.ruff]` and `[tool.ruff.lint]` blocks (E,F,UP,B,I; line-length
  100; standard ignore set).
- Run `ruff check --fix` for autofixable rules; commit the autofixes.
- Manually triage non-autofixable findings: either fix in this PR or add
  targeted `# noqa: <RULE>` with explanation. Bias toward fixing.
- Remove `flake8` from CI and any leftover `.flake8` config.
- Wire `ruff check` into `lint.yml` (blocking).
- Note: `ruff format` is **not** run in this PR — that's PR 17.

### PR 12 — codespell + pytest-sugar

- Add `codespell` to dev group; `[tool.codespell]` config.
- Add `codespell` step to `lint.yml`.
- `pytest-sugar` already added in PR 3; this PR just confirms it's active
  and tunes any defaults.

### PR 13 — basedpyright (non-blocking)

- Add `basedpyright[pydantic]` to dev group; `[tool.basedpyright]` config
  mirroring AstraLint.
- Add `basedpyright` step to `lint.yml` with `continue-on-error: true`.
- PR description includes baseline error count for reference.

### PR 14 — Fix invalid type hints + basedpyright errors

- Fix all `X or None` / `X or Y` annotations (P0 backlog item) in
  `variable.py`, `dataprovider.py`, `cda/__init__.py`, and elsewhere.
  Use `X | None` / `X | Y` (PEP 604, allowed under py3.10+).
- Fix remaining basedpyright errors flagged in PR 13.
- Where a fix is risky or non-obvious, add narrowly-scoped
  `# type: ignore[<rule>]` with a reason. Bias toward fixing.

### PR 15 — Flip basedpyright to blocking

- Remove `continue-on-error: true` from `lint.yml`.
- Tiny, mechanical PR.

### PR 16 — Coverage branch + ratcheted `fail_under`

- Add `[tool.coverage.run] branch = true`, `source = ["speasy"]`.
- Add `[tool.coverage.report]` with AstraLint's standard `exclude_lines`.
- Run unit suite, observe coverage percentage, set
  `fail_under = round(measured) - 2`.
- PR description records the measured number for future reference.

### PR 17 — Mass reformat

- Run `ruff format` over the entire repo.
- Add `.git-blame-ignore-revs` listing this commit.
- Document the file in `CONTRIBUTING.rst` so contributors configure
  `git config blame.ignoreRevsFile .git-blame-ignore-revs`.
- Mechanical, large diff, easy to review by inspecting config + spot
  checks.

---

## 6. Risks & mitigations

### Cassette drift

**Risk**: cassettes are recorded artifacts of upstream behavior at one
point in time; upstream changes silently and cassettes lie.

**Mitigation**: the contract tier (real servers, daily cron) is the
explicit watchdog. When contract fails, the affected provider's cassettes
are re-recorded as a follow-up PR. The original real-server tests survive
as the contract probes — they don't get deleted, just remarked.

### Cassette repo size

**Risk**: CDF responses are binary; cassettes can balloon the repo.

**Mitigation**: record small time ranges and decimated/light products
where possible. Budget: re-evaluate at 50 MB for `tests/cassettes/`. Move
to `git-lfs` if exceeded — handled in a single dedicated follow-up PR
rather than pre-emptively.

### First hatchling-built release

**Risk**: switching build backends can produce subtly different wheel
contents (file inclusion, metadata, entry points) that break installs in
ways flit didn't.

**Mitigation**: PR 10 includes a built-artifact diff against the last
flit-built release in the PR description. The first release after PR 10
goes to TestPyPI first; install in a fresh venv; smoke-test before
pushing to PyPI proper.

### PR 2 mass-marker diff

**Risk**: PR 2 touches every test file and is hard to review.

**Mitigation**: a one-off script in `devtools/add_test_markers.py` does
the decoration; the PR description shows the script and a sample diff.
Reviewer verifies the script logic, not 35 file diffs.

### `PYTHONPATH=. py.test` breaks post-PR 1

**Risk**: existing developer muscle memory and any external scripts that
use the `PYTHONPATH=.` pattern stop working when `__version__` becomes
metadata-driven (PR 10 introduces the issue, PR 1 introduces the
workflow change).

**Mitigation**: the `__version__` fallback in `speasy/__init__.py` makes
import-from-source still functional (returns `"0.0.0+dev"`).
Documentation update in PR 1 (`CLAUDE.md`, `CONTRIBUTING.rst`,
`Makefile`, `README.md`) documents the new workflow. Old pattern is not
preserved.

### Coverage drop after mock migration

**Risk**: some lines exercised today only by real responses may not be
hit by replayed cassettes (e.g., rare server-side branches).

**Mitigation**: the ratcheted `fail_under` (PR 16) is set after migration
completes, based on the measured post-migration number minus 2%. No
panic-blocking. New tests over time push the number up.

### Thin unit tier during migration window

**Risk**: between PR 2 (markers applied — most network-hitting tests
labelled `contract`) and PR 9 (last cassette migration done), the unit
tier per-PR coverage is mostly the existing pure-logic tests. Bugs in
provider-handling code that only surfaced via network tests won't be
caught per-PR during this window.

**Mitigation**: contract tier runs daily during this period and catches
regressions within 24 h. PRs 4–9 are sequenced to land quickly to shrink
the window. Migrating providers in order of risk (heavily used first:
AMDA, CDA) means the unit tier rebuilds coverage for the most-touched
code paths first.

### `-m unit` default surprises

**Risk**: setting `addopts = "-m unit"` in `pyproject.toml` means
`pytest tests/test_cdaweb.py` shows zero tests collected if
`test_cdaweb.py` is contract-marked.

**Mitigation**: documented in `CONTRIBUTING.rst` — running a specific
non-unit file requires `pytest -m contract tests/test_cdaweb.py` or
`pytest --no-header -p no:randomly -m '' tests/test_cdaweb.py`. A short
`make test-all` target covers the common case.

### Coordination conflicts on `pyproject.toml`

**Risk**: most PRs touch `pyproject.toml`. Rebases will conflict.

**Mitigation**: PR sequence is mostly linear; only PRs 11–15 are
parallelizable with cassette PRs (4–9), and they touch different
sections of `pyproject.toml`. Conflicts are textual, not semantic.

---

## 7. Success criteria

- Per-PR CI completes in under 5 minutes (currently 30+ min).
- A single `uv sync` provides a working dev environment.
- `uv run pytest` runs the unit tier and exits clean without network.
- Contract workflow detects an upstream change within 24 h.
- E2E workflow runs green weekly across all OS×Py combos.
- Branch coverage measured and gated.
- All P0 type-hint errors resolved; basedpyright blocks bad types.
- Releases ship via `scripts/release.sh VERSION` in one command.
- Mass reformat recorded in `.git-blame-ignore-revs`; blame stays useful.

---

## References

- AstraLint config (canonical reference for tooling stack):
  `/home/jeandet/Documents/prog/AstraLint/pyproject.toml`
- Speasy backlog (P0/P1 items addressed by this work):
  `/home/jeandet/.claude/projects/-var-home-jeandet-Documents-prog-speasy/memory/speasy-backlog.md`
- Speasy architecture overview:
  `/home/jeandet/.claude/projects/-var-home-jeandet-Documents-prog-speasy/memory/speasy-architecture.md`
- GitHub issues addressed: #236 (partial — test side), #237 (partial),
  #271 (UV adoption), #272 (skip CI on doc-only changes — incidental
  benefit via marker filter).
