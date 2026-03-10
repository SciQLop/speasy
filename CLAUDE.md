# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Speasy ("Space Physics made EASY") is a Python library providing a unified API for accessing 70+ space physics missions and 65,000+ data products from multiple web services (AMDA, CDAWeb, CSA, SSCWeb, CDPP 3DView). Built with flit, requires Python >=3.9.

## Common Commands

```bash
# Install in development mode
python -m pip install -e .
python -m pip install -r requirements_dev.txt

# Run tests
PYTHONPATH=. py.test                    # all tests
PYTHONPATH=. py.test tests/test_amda.py # single test file
PYTHONPATH=. py.test -k "test_name"     # single test by name

# Lint
flake8 speasy tests --count --select=E9,F63,F7,F82 --show-source --statistics

# Doctests
make doctest

# Build
python -m build --sdist --wheel
```

## Test Environment Variables

- `SPEASY_CORE_DISABLED_PROVIDERS` — comma-separated list of providers to disable (defaults to "" in conftest.py)
- `SPEASY_AMDA_USERNAME` / `SPEASY_AMDA_PASSWORD` — AMDA credentials
- `SPEASY_LONG_TESTS` — enable long-running tests
- `SPEASY_INVENTORY_TESTS` — enable inventory tests

## Architecture

### Data Flow

`speasy.get_data(product, start, stop)` → `core/requests_scheduling/request_dispatch.py` → appropriate `DataProvider` subclass → raw data → `SpeasyVariable` / `Catalog` / `Dataset` / `TimeTable`

### Key Modules

- **`core/dataprovider.py`** — `DataProvider` base class with `get_data()`, `update_inventory()`, `build_inventory()`
- **`core/requests_scheduling/request_dispatch.py`** — central dispatch routing products to providers
- **`data_providers/`** — six provider implementations: `amda`, `cda`, `csa`, `ssc`, `generic_archive`, `cdpp3dview`
- **`products/variable.py`** — `SpeasyVariable`, the main time-series container (~1000 lines, supports numpy ops, pandas conversion, plotting)
- **`products/`** — also contains `Catalog`, `Event`, `Dataset`, `TimeTable`
- **`core/cache/`** — disk caching via `diskcache`, request-level and provider-level caches, concurrent request deduplication
- **`core/codecs/`** — plugin architecture for format decoders (CDF/ISTP, HAPI CSV)
- **`inventories/`** — hierarchical (`data_tree.<provider>.<category>.<product>`) and flat inventory trees
- **`config/`** — env vars + INI file (`~/.config/speasy/config.ini`)

### Decorator Patterns

- `@Proxyfiable` — marks methods as cacheable via upstream proxy server
- `@Cacheable` — local disk caching
- `@ParameterRangeCheck` — validates product time ranges

### Adding a New Data Provider

Subclass `DataProvider` in `core/dataprovider.py`, implement `get_data()` and inventory methods. Register in `core/requests_scheduling/`. See `CONTRIBUTING.rst` for the full guide including codec creation.

## Conventions

- Tests use `ddt` (data-driven tests) for parameterized testing
- Version tracked in `VERSION` file, bumped with `bumpversion` (updates VERSION, pyproject.toml, `__init__.py`, docs/conf.py, CITATION.cff)
- Flake8 rules: E9, F63, F7, F82 (strict); max-complexity=10, max-line-length=127 (warnings)
- Ruff configured only for `NPY201` (numpy 2.0 deprecations)
