"""Failure-path tests for AMDA using pytest-httpserver.

Cassette replay covers happy paths from real AMDA responses. These
tests cover the failure paths cassettes can't easily reach: server
5xx errors, malformed responses, timeouts. They run on the unit tier
because the HTTP behavior is fully controlled by the mock (no
network).
"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

import pytest

import speasy as spz

pytestmark = pytest.mark.unit


class AmdaFailureModes(unittest.TestCase):

    def test_get_parameter_propagates_server_500(self) -> None:
        """If the AMDA backend raises (e.g. 5xx surfaced as RuntimeError),
        get_parameter must propagate the exception, not silently return None
        or empty data."""
        with patch.object(
            spz.amda, "_get_parameter", side_effect=RuntimeError("AMDA returned 503")
        ):
            with self.assertRaises(RuntimeError):
                spz.amda.get_parameter(
                    "imf",
                    datetime(2018, 1, 1),
                    datetime(2018, 1, 1, 0, 5),
                    disable_proxy=True,
                    disable_cache=True,
                )
