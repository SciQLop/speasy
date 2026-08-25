# Upgrade-path CI test — design

## Context

Speasy persists real state on disk between runs: a data cache, an inventory
index, and a config file, all written by whatever Speasy version the user had
installed at the time. Every existing test suite installs a single version
into a fresh environment and never touches that concern. Two recent
incidents (the [[sciqlop-cache-migration]] silently orphaning large cached
values, and the diskcache→sciqlop-cache migration bugs found while writing
docs) were both upgrade-path bugs that no test caught, because nothing
exercises "install version N, use it, upgrade to version N+1, keep using it."

This design adds a CI job that does exactly that: install an old Speasy
release, fetch some real data (populating the cache), upgrade in place, fetch
more (some of it overlapping already-cached data), and confirm nothing
crashes and the merged result is correct.

## Goals

- Catch upgrade-path regressions: a newer Speasy version failing to read
  cache/index/config state written by an older one.
- Specifically exercise **cross-version cache-fragment merging**: a single
  `get_data()` call whose result is assembled from fragments written by two
  different Speasy versions.
- Cover both a realistic **sequential** upgrade (install each intermediate
  release in turn, as `pip install --upgrade` would encounter them) and a
  realistic **direct jump** (a user who skips several releases at once —
  e.g. 1.5.x straight to the unreleased `main`/1.8.0).
- Adapt automatically to provider availability differences across versions
  (a provider added after an older curated version was released must be
  skipped there, not hardcoded as "added in version X").

## Non-goals

- Not a replacement for `tests.yml`'s per-version test matrix (which already
  covers "does this Python/OS support this *single* installed version").
  This job only cares about the *transition* between versions.
- Not a general compatibility scanner across every historical release —
  three curated versions is enough to exercise the one real backend
  transition that exists today (diskcache → sciqlop-cache, only on `main`).
- Not required-to-pass: this job is explicitly allowed to be flakier than
  `tests.yml` (old-version installs, more external network calls) without
  blocking merges.

## Architecture

### Trigger & job matrix

New workflow, `.github/workflows/upgrade_path.yml`:

```yaml
on:
  pull_request:
  schedule:
    - cron: "0 5 * * 1,4"   # twice a week

jobs:
  upgrade-path:
    continue-on-error: true   # visible, never blocks a merge
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        scenario: [sequential, direct-jump]
```

Python is pinned at **3.10** for the whole job — the oldest version every
curated release (down to 1.5.2) and `main` both support, so one venv can walk
the entire chain without a Python-version confound. (`tests.yml` already
covers newer Pythons against a single version; that's not this job's job.)

### Version list (hand-curated)

```yaml
versions: ["1.5.2", "1.7.1", "main"]
```

`1.7.1` is the newest actual PyPI release (tagged 2025-12-18); the
sciqlop-cache backend migration only exists on unreleased `main` (1.8.0-dev).
So every released version today is still diskcache-only — the one real
backend transition in Speasy's history happens exactly at the `main` step.
This list is refreshed by hand, occasionally, by glancing at
<https://sciqlop.lpp.polytechnique.fr/stats/> for which versions are still in
meaningful use. No automated scraping: the stats page is a JS dashboard, not
a stable API, and a scraper would be a maintenance burden disproportionate to
"pick 2-3 version strings every few months."

### Scenarios

Both scenarios run the *same* fetch script (see below) at each step; they
differ in which versions are installed and in what order, within one
persistent `$HOME`/venv per job (GitHub Actions keeps the same filesystem
across steps in a single job, so cache/index/config persist naturally — no
extra env vars needed to wire that up):

- **sequential**: `1.5.2` → run script (step 0) → `pip install --upgrade
  speasy==1.7.1` → run script (step 1) → checkout + install `main` from the
  working tree → run script (step 2).
- **direct-jump**: fresh `$HOME`/venv, `1.5.2` → run script (step 0) →
  install `main` directly, skipping `1.7.1` → run script (step 1). This is
  the "a user who upgrades once every N months and skips releases" case.

A step's script failing stops that job (a real user's broken upgrade doesn't
get retried automatically either); the job goes red, `continue-on-error`
keeps it non-blocking.

### The fetch script

One script, unchanged across every version/step, using only the long-stable
`spz.get_data(product, start, stop)` surface (the same call shown in
`README.md`'s own doctested examples). Two things make it exercise the
upgrade path specifically, not just "does get_data still work":

**1. Provider availability probe.** Before touching a provider, check
`provider in spz.list_providers()` (stable back to 1.5.2) and skip with a
log line if absent, instead of hardcoding which version added which
provider. Confirmed concrete case: `cdpp3dview` was added 2026-01-07, *after*
`1.7.1` was tagged — it doesn't exist at all in either curated old version,
only on `main`. A hardcoded table would need updating every time a provider
is added; the runtime probe doesn't.

**2. Growing, overlapping time window — deliberately engineered for AMDA.**
AMDA's cache fragments are a fixed, hardcoded 12-hour duration
(`fragment_hours=lambda x: 12` on the `@Cacheable` decorator in
`speasy/data_providers/amda/ws.py`) — not configurable by any env var.
(`max_chunk_size_days`, default 10, is unrelated: it only chunks the HTTP
*download* request for missing data, not the cache fragment size.) A
growing multi-day request window naturally spans multiple 12-hour fragments
on its own, so no env var is needed. For `amda/imf` (reused from the
README's own example, not a novel pick), each step *i* requests
`[start, start + (i + 2) * 1 day)` from a fixed anchor `start`. This means:
  - every single call spans **at least two cache fragments** (the "two cache
    entries" case), and
  - every step after the first **reuses at least one fragment already
    cached by the previous, older Speasy version**, and fetches+merges a new
    one written by the current version — a real cross-version cache-fragment
    merge, not just "the cache database opens without crashing."

The other providers (CDA, SSC, CSA, and `cdpp3dview` once available) get a
plain single-shot `get_data()` call each step with one small known-good
product — still real cross-version compat coverage (does this provider's
cached fragment format, whatever size it is, still read back correctly after
an upgrade), just not the deliberately-engineered multi-fragment/cross-version
merge that AMDA gets. Extending the same trick to another provider would mean
finding that provider's own hardcoded `fragment_hours` value first — there is
no configurable chunk-size knob for any provider.

Each provider/product call asserts the returned variable is non-`None` and
non-empty. AMDA credentials reuse the existing `SPEASY_AMDA_USERNAME`/
`SPEASY_AMDA_PASSWORD` secrets already wired into `tests.yml`. All other
settings stay default (proxy on, cache on) — that's what a real user's
environment looks like.

## Error handling

- A step (a single version's script run) failing: `set -e`-style hard stop
  for that job/scenario/OS cell; the job goes red, nothing else is retried.
  `continue-on-error: true` at the job level keeps this from blocking PRs.
- Old-version install failures (PyPI resolution, transient network) are a
  distinct failure mode from an actual upgrade-path bug; the design doesn't
  try to distinguish them automatically — a human reading a red run does.
  This is exactly why the job is non-blocking rather than required.

## Testing this workflow itself

CI workflow YAML has no unit-test story in this repo today (matches
`tests.yml`, `wasm_tests.yml`, etc. — none are tested, only run). The fetch
script itself is small enough to sanity-check locally with the currently
installed dev version before relying on CI to validate the workflow
plumbing (matrix expansion, secret wiring, `continue-on-error`).

## Open follow-ups (explicitly out of scope for the first version)

- Automating version-list discovery from the proxy stats page, if it ever
  gets a real API.
- Extending the curated list once a second released version exists on the
  sciqlop-cache backend (today there's only one meaningful transition to
  test: diskcache → sciqlop-cache, at the `main` step).
