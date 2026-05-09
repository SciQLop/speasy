"""Smoke tests for the test infrastructure itself.

Confirms the pytest-recording / pytest-httpserver / cache / factory
fixtures from conftest.py work as advertised. These run in the unit
tier — no network, no real servers.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.unit


def test_disable_proxy_autouse_active_for_unit_tier() -> None:
    """The autouse fixture in conftest must set SPEASY_PROXY_ENABLED=false
    before this unit-marked test runs."""
    assert os.environ.get("SPEASY_PROXY_ENABLED") == "false"


def test_tmp_speasy_cache_creates_isolated_dir(tmp_speasy_cache) -> None:
    assert tmp_speasy_cache.is_dir()
    assert os.environ["SPEASY_CACHE_PATH"] == str(tmp_speasy_cache)
    # Two test invocations must not share the directory.
    canary = tmp_speasy_cache / "canary"
    canary.write_text("hello")
    assert canary.read_text() == "hello"


def test_speasy_variable_factory_default(speasy_variable_factory) -> None:
    v = speasy_variable_factory()
    # SpeasyVariable reshapes 1D arrays to (-1, 1) for pandas consistency.
    assert v.values.shape == (10, 1)
    assert v.time.shape == (10,)


def test_speasy_variable_factory_multi_column(speasy_variable_factory) -> None:
    v = speasy_variable_factory(n_points=5, n_columns=3)
    assert v.values.shape == (5, 3)
    assert len(v.columns) == 3


def test_httpserver_fixture_serves_a_response(httpserver) -> None:
    """pytest-httpserver provides an in-process HTTP endpoint.

    Used in PRs 4-9 for surgical control over failure paths (timeouts,
    5xx, malformed bodies) where cassette replay is too coarse.
    """
    import urllib.request

    httpserver.expect_request("/ping").respond_with_data("pong", content_type="text/plain")
    with urllib.request.urlopen(httpserver.url_for("/ping"), timeout=5) as r:
        body = r.read().decode()
    assert body == "pong"
