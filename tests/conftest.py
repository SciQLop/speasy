"""Shared fixtures for the Speasy test suite.

Marker tiers (see CONTRIBUTING.rst):

- ``unit``: deterministic, no network. Default tier for ``pytest``.
- ``contract``: real-server probes for upstream-drift detection.
- ``e2e``: end-to-end smoke tests on the full OS/Python matrix.

Cassette playback for the unit tier is provided by ``pytest-recording``.
By default cassettes are replay-only — pytest-recording's session
fixture defaults ``record_mode`` to ``"none"`` so a missing cassette
fails the test rather than silently calling out to the live server.
To (re-)record:

    uv run pytest -m unit --record-mode=once
    uv run pytest -m unit --record-mode=rewrite   # force re-record
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Provider availability defaults (existing behaviour — keep)
# ---------------------------------------------------------------------------

if "SPEASY_CORE_DISABLED_PROVIDERS" not in os.environ:
    os.environ["SPEASY_CORE_DISABLED_PROVIDERS"] = ""


# ---------------------------------------------------------------------------
# Cassette storage configuration
# ---------------------------------------------------------------------------

CASSETTE_BASE_URL = "https://sciqlop.lpp.polytechnique.fr/data/speasy_cassettes"
LOCAL_CACHE = (
    Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    / "speasy-tests"
    / "cassettes"
)
TESTS_DIR = Path(__file__).parent
MANIFEST_PATH = TESTS_DIR / "cassettes_manifest.json"
CASSETTE_OUT_DIR = TESTS_DIR / "cassettes"


def _fetch_cassette(sha: str) -> Path:
    """Download a cassette by its content hash, cache locally, return path to .yaml.gz.

    Cassettes are served publicly (no auth) at CASSETTE_BASE_URL. Content
    addressing (sha256) makes the file names unguessable for outsiders
    and tamper-evident on download.
    """
    cached = LOCAL_CACHE / f"{sha}.yaml.gz"
    if cached.exists():
        # Verify integrity (defensive — corrupted cache yields a clear error).
        with gzip.open(cached, "rb") as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        if actual_sha == sha:
            return cached
        cached.unlink()

    import requests

    url = f"{CASSETTE_BASE_URL}/{sha}.yaml.gz"
    LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    decompressed = gzip.decompress(response.content)
    actual_sha = hashlib.sha256(decompressed).hexdigest()
    if actual_sha != sha:
        raise RuntimeError(
            f"Hash mismatch for {sha[:12]}...: server returned {actual_sha[:12]}..."
        )
    cached.write_bytes(response.content)
    return cached


def _populate_cassettes() -> None:
    """Read the manifest, ensure every cassette is on disk under tests/cassettes/."""
    if not MANIFEST_PATH.exists():
        return
    manifest = json.loads(MANIFEST_PATH.read_text() or "{}")
    if not manifest:
        return

    for rel_path, sha in manifest.items():
        dest = CASSETTE_OUT_DIR / rel_path
        if dest.exists():
            actual = hashlib.sha256(dest.read_bytes()).hexdigest()
            if actual == sha:
                continue
        cached_gz = _fetch_cassette(sha)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(cached_gz, "rb") as src, open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--no-cassette-fetch",
        action="store_true",
        default=False,
        help="Skip fetching cassettes from sciqlop.lpp; rely on whatever is already on disk.",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--no-cassette-fetch"):
        return
    try:
        _populate_cassettes()
    except Exception as exc:
        # Fail loudly: print and re-raise. Don't silently fall back.
        print(f"\nERROR populating cassettes from {CASSETTE_BASE_URL}: {exc}", file=sys.stderr)
        raise


# ---------------------------------------------------------------------------
# pytest-recording / VCR configuration
# ---------------------------------------------------------------------------

CASSETTE_ROOT = CASSETTE_OUT_DIR


_AMDA_AUTH_TOKEN_RE = re.compile(rb"^[0-9a-f]{32}$")


def _scrub_response(response):
    """Strip credential-shaped data from RESPONSE side before recording.

    vcrpy's ``filter_headers`` and ``filter_query_parameters`` only scrub
    the REQUEST side. Response headers like ``Set-Cookie`` (session
    identifiers) and certain response bodies (AMDA's ``auth.php`` returns
    a 32-char hex hash that may be derivable from credentials) need
    explicit scrubbing here.
    """
    headers = response.get("headers") or {}
    for name in list(headers):
        if name.lower() in {"set-cookie", "cookie"}:
            headers.pop(name)

    body = response.get("body") or {}
    raw = body.get("string")
    if isinstance(raw, (bytes, bytearray)) and _AMDA_AUTH_TOKEN_RE.match(raw):
        body["string"] = b"<SCRUBBED>"
    elif isinstance(raw, str) and _AMDA_AUTH_TOKEN_RE.match(raw.encode()):
        body["string"] = "<SCRUBBED>"
    return response


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, Any]:
    """Default VCR config: scrub auth-bearing headers/params/responses.

    The filter lists are deliberately broad to avoid accidentally
    committing secrets into cassette YAML files. When PRs 4-9 record
    real-server interactions, anything matching these names in headers
    or query strings is replaced with a placeholder before the cassette
    is written to disk.

    The ``before_record_response`` callback handles response-side leaks
    that ``filter_headers``/``filter_query_parameters`` don't reach:
    ``Set-Cookie`` session IDs and AMDA's ``auth.php`` response token
    (32-char hex hash).

    ``record_mode`` is intentionally NOT set here — pytest-recording's
    session fixture defaults it to ``"none"`` (replay-only) and lets
    the ``--record-mode`` CLI flag override that default. Setting it
    in this dict would unconditionally clobber the CLI flag and make
    re-recording impossible.
    """
    return {
        "filter_headers": [
            "authorization",
            "bearer",
            "cookie",
            "set-cookie",
            "x-api-key",
        ],
        "filter_query_parameters": [
            "apikey",
            "api_key",
            "password",
            "sessionID",
            "token",
            "userID",
        ],
        "before_record_response": _scrub_response,
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
    """Set ``SPEASY_CACHE_PATH`` to a per-test tempdir.

    .. warning::

        Speasy's disk cache is a module-level singleton constructed at
        import time (``speasy.core.cache._instance._cache``). Once
        ``speasy.core.cache`` has been imported in the test session,
        the cache is bound to the path it saw at first import — and
        monkeypatching ``SPEASY_CACHE_PATH`` afterwards has no effect
        on the live ``_cache`` object.

        This fixture is therefore only effective for code paths that
        re-read ``SPEASY_CACHE_PATH`` dynamically (e.g. tests that
        construct their own ``Cache(...)`` rather than using the
        package-level singleton). For tests needing real isolation of
        the singleton, the cassette-migration PRs will introduce a
        sturdier mechanism (e.g. monkeypatching the singleton itself).
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
# Canonical HTTP rewrite rule for vcr-replayed tests
# ---------------------------------------------------------------------------

# Cassettes are recorded under a specific rewrite-rule policy: the placeholder
# host ``thisserver_does_not_exists.lpp.polytechnique.fr/pub/`` is rewritten to
# the LPP CDA mirror; ``cdaweb.gsfc.nasa.gov`` is NOT rewritten. Users may have
# their own ``http_rewrite_rules`` in ``~/.config/speasy/config.ini`` (e.g.,
# rewriting cdaweb.gsfc.nasa.gov to a local mirror) — that would break replay
# because the replay-side URL would no longer match the cassette. Force the
# recording-time rewrite policy for any vcr-marked test so replay is
# deterministic regardless of the developer's local config.
_VCR_REWRITE_RULES = {
    "https://thisserver_does_not_exists.lpp.polytechnique.fr/pub/":
        "http://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/",
}


@pytest.fixture(autouse=True)
def _canonical_rewrite_rule_for_vcr(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin the HTTP rewrite-rule dict to the recording-time value for any
    vcr-marked test so cassette replay matches regardless of the developer's
    ``~/.config/speasy/config.ini``.

    Speasy caches ``_REWRITE_RULES_`` at module import time in
    ``speasy.core.url_utils``, so setting the env var alone has no effect once
    the module is loaded. We monkeypatch the cached dict directly.
    """
    if "vcr" in request.keywords:
        import speasy.core.url_utils
        monkeypatch.setattr(
            speasy.core.url_utils, "_REWRITE_RULES_", _VCR_REWRITE_RULES
        )


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

    import numpy as np

    from speasy.core.data_containers import (
        DataContainer,
        VariableTimeAxis,
    )
    from speasy.products import SpeasyVariable

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
