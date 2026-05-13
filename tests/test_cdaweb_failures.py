"""Failure-path tests for CDA using mocked HTTP responses.

Cassette replay covers happy paths from real CDA responses. These
tests cover failure paths cassettes cannot easily reach: server 5xx
errors. They run on the unit tier because the HTTP behaviour is
fully controlled by the mock (no network).
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import speasy as spz
from speasy.data_providers.cda import CdaWebException

pytestmark = pytest.mark.unit


def _fake_http_response(status: int, body: bytes = b'{"Message": ["Internal error"]}') -> MagicMock:
    """Build a minimal stand-in for the speasy ``Response`` returned by
    ``speasy.core.http.get`` so the CDA wrapper sees a 5xx with a JSON
    body it can parse."""
    resp = MagicMock()
    resp.status_code = status
    resp.ok = False
    resp.url = "https://cdaweb.gsfc.nasa.gov/WS/cdasr/1/fake"
    resp.json.return_value = {"Message": ["Internal error"]}
    resp.bytes = body
    resp.text = body.decode()
    return resp


class CdaFailureModes(unittest.TestCase):

    def test_get_variable_propagates_server_500(self) -> None:
        """A 500 from CDA must surface as ``CdaWebException`` so callers can
        distinguish a server error from a legitimate "no data" response."""
        with patch(
            "speasy.data_providers.cda.http.get",
            return_value=_fake_http_response(500),
        ):
            with self.assertRaises(CdaWebException):
                spz.cda.get_variable(
                    dataset="THA_L2_FGM",
                    variable="tha_fgl_gsm",
                    start_time=datetime(2014, 6, 1, tzinfo=timezone.utc),
                    stop_time=datetime(2014, 6, 1, 0, 5, tzinfo=timezone.utc),
                    disable_proxy=True,
                    disable_cache=True,
                    method="API",
                )


if __name__ == "__main__":
    unittest.main()
