#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.core.impex.client`."""
import unittest
from unittest.mock import Mock, patch

from speasy.core.impex.client import ImpexClient, ImpexEndpoint
from speasy.core.impex.exceptions import InvalidCredentials


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

    def test_timetable_and_catalog_ignore_parameter_options(self):
        # a data index replays the stored request options (e.g. AMDA's restricted_period) to refresh a timetable
        client = ImpexClient(server_url="http://impex.example.org",
                             capabilities=[ImpexEndpoint.GETTT, ImpexEndpoint.GETCAT])
        options = {'restricted_period': False, 'output_format': 'cdf', 'product_inputs': {'lookdir': '4'}}
        with patch.object(client, '_send_request', return_value="http://file") as send:
            self.assertEqual(client.get_timetable("tt_1", **options), "http://file")
            self.assertEqual(client.get_catalog("cat_1", **options), "http://file")
        for call in send.call_args_list:
            self.assertEqual(set(call.kwargs), {'params'})

    def test_rejected_login_raises_a_clear_error(self):
        client = ImpexClient(server_url="http://impex.example.org", capabilities=[ImpexEndpoint.LISTTT],
                             username="bad", password="bad", provider_name="amda")
        response = Mock(status_code=200)
        response.json.return_value = {"error": "Login procedure failed for bad : Check your password"}
        with patch('speasy.core.impex.client.http.get', return_value=response):
            with self.assertRaisesRegex(InvalidCredentials, r"amda rejected.*'bad'.*SPEASY_AMDA_USERNAME"):
                client.get_time_table_list(use_credentials=True)


if __name__ == '__main__':
    unittest.main()
