# Speasy Backlog

Tracked items from the March 2026 project review. Check off items as they are completed.

---

## P0 — Must Fix

- [ ] **Import-time hang when server is down** — `import speasy` blocks ~6 min when AMDA is unreachable. Add short timeout on provider init + graceful degradation. (GH #236)
- [ ] **Fix invalid type hint syntax** — `X or None` and `X or Y` used instead of `Optional[X]` / `Union[X, Y]` throughout `variable.py`, `dataprovider.py`, `cda/__init__.py`. These are not valid for static type checkers.
- [ ] **Remove bare except** in `core/proxy/__init__.py:77` — catches `SystemExit`/`KeyboardInterrupt`.
- [ ] **Remove debug `print(e)`** in `core/proxy/__init__.py:159` — should use `log.error` only.
- [ ] **Remove dead code** in `core/http.py:178-187` — commented-out `TimeoutHTTPAdapter`.

## P1 — High Priority

### Robustness

- [ ] **Offline mode** — allow using cached data when servers are unreachable. (GH #237)
- [ ] **Narrow broad exception handlers** — `request_dispatch.py:88` and `_providers_caches.py:193,230,288,374` swallow all exceptions silently. Catch specific types, log properly.
- [ ] **Improve error messages** — `cda/__init__.py:173` wraps HTTP status without product/time context. Add request details to all provider error messages.

### Testing

- [ ] **Add mock-based provider tests** — most tests hit real servers (`disable_cache=True, disable_proxy=True`). Add `responses` or `requests-mock` based tests for all 6 providers.
- [ ] **Re-enable CDPP 3DView in CI** — currently globally disabled in `tests.yml:14`.
- [ ] **Add Python 3.9 to CI matrix** — minimum supported version per `pyproject.toml` but not tested.
- [ ] **Add tests for plotting module** — `speasy/plotting/` has zero test coverage.
- [ ] **Add tests for `core/proxy/`** — only 1 test exists currently.
- [ ] **Add tests for `core/requests_scheduling/`** — no dedicated tests for dispatch or request splitting.
- [ ] **Build proper conftest.py** — add shared fixtures, `SpeasyVariable` factories, mock HTTP infrastructure.

### Code Quality

- [ ] **Split `SpeasyVariable`** — 1085 lines, 70+ methods. Extract numpy interop, pandas conversion, plotting, serialization into mixins or helper modules.
- [ ] **Reduce global mutable state** — `request_dispatch.py` uses module-level globals (`amda = None`, etc.) initialized on import. `dataprovider.py` has global `PROVIDERS = {}`. Consider lazy initialization or dependency injection.

## P2 — Medium Priority

### Features (from GH issues)

- [ ] **HAPI client** — significant missing capability. (GH #153, #181-185)
- [ ] **Virtual products / user-defined functions** — computed products support. (GH #186, #187, #188)
- [ ] **PySPEDAS interface** — interop with another major space physics tool. (GH #235)
- [ ] **NetCDF codec** (GH #209)
- [ ] **CLWeb support** (GH #190)
- [ ] **SuperMAG provider** (GH #116)

### Security

- [ ] **Keyring integration for credentials** — AMDA username/password stored as plaintext in `~/.config/speasy/config.ini`. Consider `keyring` library or at minimum warn users.
- [ ] **Atomic config writes** — `config/__init__.py` writes on every `ConfigEntry.set()`, risking corruption on concurrent access.

### Documentation

- [ ] **Expand thin provider docs** — CDAWeb (48 lines), CSA (33 lines), SSCWeb (43 lines), CDPP3DView (37 lines) vs AMDA (275 lines).
- [ ] **Document optional dependencies** — `zstd` extra is undocumented.
- [ ] **Add troubleshooting/FAQ section** to docs.
- [ ] **Standardize inventory API references** — docs mix `data_tree` and `tree` aliases inconsistently.
- [ ] **Fix CONTRIBUTING.rst:113** — references `README.rst` but file is `README.md`.
- [ ] **Expand configuration docs** — missing HTTP proxy, logging, HTTP auth sections.
- [ ] **Add `uiowaephtool` to `__all__`** and document it properly.

### Infrastructure

- [ ] **Switch to UV for dev workflow** (GH #271)
- [ ] **Skip CI on doc-only changes** (GH #272)
- [ ] **Switch to SciQLop cache** (GH #275)
- [ ] **Add mypy to CI** — type hints exist but are never checked.

## P3 — Nice to Have

- [ ] **Plugin architecture for providers** — make providers installable separately. (GH #273)
- [ ] **Exportable persistent data index** — alternative to cache for offline use. (GH #122)
- [ ] **HTML repr for notebooks** (GH #8)
- [ ] **Download job manager** (GH #37)
- [ ] **More example notebooks** (GH #31)
- [ ] **Improve Caches notebook** (GH #32)
- [ ] **Upper-bound dependency pinning** — no upper bounds on 15 of 17 deps.
- [ ] **Evaluate mabain as diskcache alternative** (GH #198)
- [ ] **Refactor decorator stacking** — `cda/__init__.py:177-179` stacks 3 complex decorators; execution order is non-obvious.
- [ ] **Refactor `core/impex/`** — mixes data fetching, XML parsing, inventory management, and credential handling in one class.
- [ ] **Expose `list_providers()` and `config`** in public API.
- [ ] **Basic plot schema across tools** (GH #107)

---

*Generated from project review on 2026-03-10.*
