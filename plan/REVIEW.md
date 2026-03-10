# Speasy Project Review

## Overview

Speasy is a well-conceived Python library solving a real pain point in space physics: unified access to 70+ missions and 65,000+ products across 6 data providers (AMDA, CDAWeb, CSA, SSCWeb, Direct Archive, CDPP 3DView). The project has a DOI (Zenodo), runs on PyPI, has ReadTheDocs, and offers interactive notebooks via MyBinder and Google Colab. It's a serious, useful scientific tool.

**GitHub stats**: 38 open issues, 1 open PR, active development with recent commits. Primarily a solo/small-team project (author: Alexis Jeandet), with external contributions (co-libri-org for CDPP3DView and HAPI codec).

---

## Strengths

### Clean top-level API

```python
import speasy as spz
data = spz.get_data("amda/imf", "2021-01-01", "2021-01-02")
```

The API is simple and does what it promises. The inventory tree with tab-completion (`spz.inventories.data_tree.cda.MMS...`) is excellent for discovery.

### Solid architecture

- Clear separation: providers, products, cache, codecs, inventory
- Decorator patterns (`@Proxyfiable`, `@Cacheable`, `@SplitLargeRequests`) enable composable behavior
- Community proxy server for performance optimization
- Codec plugin system for format extensibility

### Good documentation

- Excellent README with working examples
- 10 Jupyter notebook examples
- Provider-specific guides
- Well-maintained HISTORY.rst with PR links

### Practical features

- Disk caching with `diskcache`
- NumPy/pandas interoperability on `SpeasyVariable`
- Signal processing (resampling, filtering via SciPy)
- WASM/Pyodide support (impressive for a science library)

---

## Weaknesses & Issues Found

### 1. Code Quality

**`SpeasyVariable` is a god class** (`speasy/products/variable.py`, 1085 lines, 70+ methods). It handles time-series operations, numpy interop, pandas conversion, plotting, serialization, and validation all in one class. This is the single biggest maintainability concern.

**Invalid type hint syntax throughout**:

```python
# variable.py:365 - not valid Python type syntax
def __array_ufunc__(self, ...) -> 'SpeasyVariable' or None:
# variable.py:67 - not a valid Union
axes: List[VariableAxis or VariableAxis]
# dataprovider.py:97
def get_data(self, product: str or ParameterIndex, ...):
```

These don't work with mypy or any static type checker. `Optional[SpeasyVariable]` and `Union[str, ParameterIndex]` are needed.

**Debug artifact in production code** — `speasy/core/proxy/__init__.py:159`:

```python
except Exception as e:
    log.error(...)
    print(e)  # <-- bare print in exception handler
```

**Commented-out dead code** in `speasy/core/http.py:178-187` (TimeoutHTTPAdapter implementation).

### 2. Error Handling

**Bare except** in `speasy/core/proxy/__init__.py:77`:

```python
except:  # lgtm [py/catch-base-exception]
```

Catches `SystemExit` and `KeyboardInterrupt`. The LGTM annotation acknowledges but doesn't fix it.

**Broad exception swallowing** in `speasy/core/requests_scheduling/request_dispatch.py:88`:

```python
except Exception:  # pylint: disable=broad-except
    log.warning(f"Provider {names} initialization failed, disabling provider")
```

This masks import errors, credential errors, and network timeouts equally. Users get a vague "initialization failed" message.

**Silent cache corruption** in `speasy/core/cache/_providers_caches.py:193-195` — returns `None` when cache deserialization fails without proper logging.

### 3. The Import-Time Hang Bug (Issue #236)

This is a real usability problem. When AMDA is down, `import speasy` hangs for ~6 minutes before crashing with `ResponseError: too many 502 error responses`. For users who only want cached data, this is a blocker. Issue #237 proposes an offline mode, but it's been open since 2025-09 with no implementation.

### 4. Test Suite

**Network-dependent tests without mocking**: Most provider tests hit real servers with `disable_cache=True, disable_proxy=True`. Only 2 test files use `mock`. This makes tests inherently flaky — any server downtime breaks CI.

**Notable gaps**:

| Module | Test Coverage |
|--------|--------------|
| `speasy/plotting/` | **Zero tests** |
| `speasy/core/proxy/` | 1 test only |
| `speasy/core/requests_scheduling/` | No dedicated tests |
| `speasy/core/impex/` | Only credential exception tests |
| Generic Archive Provider | No dedicated tests |

**CDPP 3DView disabled in CI** (`tests.yml:14`: `SPEASY_CORE_DISABLED_PROVIDERS: "cdpp3dview"`), meaning one of the 6 providers is never tested in CI.

**Python 3.9 not tested** despite `requires-python = ">=3.9"` in pyproject.toml. CI starts at 3.10.

**conftest.py is 4 lines** — no shared fixtures, no test factories, no mock infrastructure.

### 5. Security

**Plaintext credentials**: AMDA username/password stored in `~/.config/speasy/config.ini` as plain text. No encryption, no keyring integration, no warning about this.

**Proxy URL credentials**: `speasy/core/http.py:45-46` reads HTTP_PROXY from environment without sanitizing potential embedded credentials.

### 6. Architecture Concerns

**Global mutable state**: Providers are registered in a global `PROVIDERS = {}` dict during `__init__`, and `request_dispatch.py` uses module-level globals (`amda = None`, `csa = None`, etc.) initialized on import. This makes testing harder and is the root cause of the import-hang bug.

**Implicit proxy fallback**: The `@Proxyfiable` decorator silently falls back to direct fetch if the proxy fails. Users never know which path was taken, making debugging difficult.

**Config writes are not atomic**: `speasy/config/__init__.py` writes to disk on every `ConfigEntry.set()` — could corrupt config during concurrent access.

### 7. Dependencies

17 runtime dependencies including heavy ones (astropy, astroquery, matplotlib, scipy, pandas). No upper bounds on any of them except `urllib3>=1.26.0` and `pyistp>=0.7.2`. The `zstd` optional dependency is completely undocumented.

### 8. Documentation Gaps

- **CDAWeb, CSA, SSCWeb docs are thin** (33-48 lines each vs AMDA's 275 lines)
- **Inventory API referenced inconsistently** (`data_tree` vs `tree` alias used interchangeably)
- **No troubleshooting/FAQ section**
- **CONTRIBUTING.rst:113** references `README.rst` but the file is `README.md`
- **`uiowaephtool`** provider not in `__all__` and poorly documented
- **Configuration guide** missing sections on HTTP proxy details, logging, HTTP auth

---

## Open Issues Themes

**Feature requests** (majority of the 38 open issues):

- **HAPI client** (#153, plus #181-185 for infrastructure) — a significant missing capability
- **Virtual products / user-defined functions** (#186, #187, #188) — would enable computed products
- **Offline mode** (#237) — critical for reliability
- **Plugin architecture** (#273) — modularity improvement
- **PySPEDAS interface** (#235) — interoperability with another major space physics tool

**Infrastructure**:

- Switch to SciQLop cache (#275), UV for devs (#271), skip CI for doc-only changes (#272)
- Evaluate mabain as diskcache alternative (#198)

**Long-standing** (2+ years old):

- HTML repr for notebooks (#8, 2022)
- Document config (#42, 2022)
- More example notebooks (#31, 2022)
- Download job manager (#37, 2022)

---

## Recommendations (Prioritized)

### Must-fix

1. **Fix the import-hang bug** — at minimum, add a short timeout on provider initialization and graceful degradation when servers are unreachable
2. **Fix invalid type hint syntax** — these are actual Python errors in type annotations
3. **Remove bare except and debug print statements**

### High priority

4. **Add mock-based tests** for all providers to decouple from network
5. **Re-enable CDPP 3DView in CI** and add Python 3.9 to the test matrix
6. **Implement offline mode** (#237) — this is the most requested feature and a real user pain point
7. **Split `SpeasyVariable`** into smaller, focused classes (or use mixins)

### Medium priority

8. **HAPI client** (#153) — would significantly expand data access
9. **Keyring integration** for credentials instead of plaintext config
10. **Expand thin provider docs** (CDAWeb, CSA, SSCWeb)
11. **Add a proper conftest.py** with fixtures and test factories
12. **Document optional dependencies** and add a troubleshooting FAQ

### Nice to have

13. Plugin architecture for providers (#273)
14. Virtual products (#186)
15. Atomic config writes
16. Upper-bound dependency pinning

---

## Overall Assessment

Speasy is a **well-designed, genuinely useful library** that solves a hard problem (unified space physics data access) with an elegant API. The architecture is sound, the documentation is above average for a scientific Python project, and the WASM support shows forward-thinking.

The main concerns are **operational robustness** (import hangs, no offline mode, flaky tests), **code maintainability** (god class, invalid type hints, swallowed exceptions), and **test infrastructure** (network-dependent, minimal mocking, coverage gaps). These are typical of a project that has grown organically from a research tool into something with real users — the core design is good, but it needs hardening.
