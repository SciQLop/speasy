#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.core.impex.client`."""
import unittest
from unittest.mock import patch

from speasy.core.impex.client import ImpexClient, ImpexEndpoint


class ImpexClientTest(unittest.TestCase):
    def setUp(self):
        self.client = ImpexClient(server_url="http://impex.example.org",
                                  capabilities=[ImpexEndpoint.OBSTREE])

    def test_send_indirect_request_returns_none_when_server_unreachable(self):
        # https://github.com/SciQLop/speasy/issues/228
        # When the server is unreachable, _send_request already returns None.
        # _send_indirect_request must not crash trying to parse that as a URL.
        with patch.object(self.client, '_send_request', return_value=None):
            result = self.client._send_indirect_request(ImpexEndpoint.OBSTREE)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
