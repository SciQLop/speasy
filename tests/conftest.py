"""Shared fixtures for the Speasy test suite.

Marker tiers (see CONTRIBUTING.rst):

- ``unit``: deterministic, no network. Default tier for ``pytest``.
- ``contract``: real-server probes for upstream-drift detection.
- ``e2e``: end-to-end smoke tests on the full OS/Python matrix.

Cassette playback for the unit tier is provided by ``pytest-recording``.
By default cassettes are replay-only — the `vcr_config` fixture sets
``record_mode = "none"`` so a missing cassette fails the test rather
than silently calling out to the live server. To (re-)record:

    uv run pytest -m unit --record-mode=once
    uv run pytest -m unit --record-mode=rewrite   # force re-record
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Provider availability defaults (existing behaviour — keep)
# ---------------------------------------------------------------------------

if "SPEASY_CORE_DISABLED_PROVIDERS" not in os.environ:
    os.environ["SPEASY_CORE_DISABLED_PROVIDERS"] = ""


# ---------------------------------------------------------------------------
# pytest-recording / VCR configuration
# ---------------------------------------------------------------------------

CASSETTE_ROOT = Path(__file__).parent / "cassettes"


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, Any]:
    """Default VCR config: replay only, scrub auth-bearing headers/params."""
    return {
        "filter_headers": ["authorization", "cookie", "set-cookie"],
        "filter_query_parameters": ["userID", "password", "token"],
        "record_mode": "none",
    }


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    """Place cassettes alongside the test module: tests/cassettes/<module>/."""
    module_name = Path(request.module.__file__).stem
    return str(CASSETTE_ROOT / module_name)


# ---------------------------------------------------------------------------
# Cache isolation
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_speasy_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Isolate Speasy's disk cache to a per-test tempdir.

    Without this fixture, tests share a single cache directory and can
    interact in unexpected ways when run in parallel or in different orders.
    Set the ``SPEASY_CACHE_PATH`` env var before any speasy module that
    uses the cache is imported in the test body.
    """
    cache_dir = tmp_path / "speasy_cache"
    cache_dir.mkdir()
    monkeypatch.setenv("SPEASY_CACHE_PATH", str(cache_dir))
    return cache_dir


# ---------------------------------------------------------------------------
# Disable SciQLop proxy for unit-tier tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _disable_proxy_for_unit_tier(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unit tests must not be silently satisfied by a hot SciQLop proxy hit.

    Sets ``SPEASY_PROXY_ENABLED=false`` for any test marked ``unit``.
    Contract and e2e tests keep the proxy enabled (the proxy speeds them
    up and is part of the real path users exercise).
    """
    if "unit" in request.keywords:
        monkeypatch.setenv("SPEASY_PROXY_ENABLED", "false")


# ---------------------------------------------------------------------------
# SpeasyVariable factory
# ---------------------------------------------------------------------------

SpeasyVariableFactory = Callable[..., "speasy.products.SpeasyVariable"]  # type: ignore[name-defined]  # noqa: F821


@pytest.fixture
def speasy_variable_factory() -> SpeasyVariableFactory:
    """Build a minimal ``SpeasyVariable`` for unit tests.

    Usage::

        def test_something(speasy_variable_factory):
            v = speasy_variable_factory(n_points=100, n_columns=3)
            assert v.values.shape == (100, 3)
    """

    from datetime import datetime, timedelta, timezone

    from speasy.products import SpeasyVariable
    from speasy.core.data_containers import (
        DataContainer,
        VariableTimeAxis,
    )

    def _make(
        n_points: int = 10,
        n_columns: int = 1,
        start: datetime = datetime(2020, 1, 1, tzinfo=timezone.utc),
        cadence: timedelta = timedelta(seconds=1),
        name: str = "test_variable",
        unit: str = "",
        dtype: Any = np.float64,
    ) -> SpeasyVariable:
        time_values = np.array(
            [int((start + cadence * i).timestamp() * 1e9) for i in range(n_points)],
            dtype="datetime64[ns]",
        )
        time_axis = VariableTimeAxis(values=time_values)
        if n_columns == 1:
            data = np.arange(n_points, dtype=dtype)
        else:
            data = np.tile(
                np.arange(n_points, dtype=dtype).reshape(-1, 1), (1, n_columns)
            )
        values = DataContainer(values=data, name=name, meta={"UNITS": unit})
        return SpeasyVariable(axes=[time_axis], values=values, columns=[
            f"{name}_{i}" for i in range(n_columns)
        ] if n_columns > 1 else [name])

    return _make
