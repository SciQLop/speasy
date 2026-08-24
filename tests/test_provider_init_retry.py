#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the failed-provider-init retry added to update_inventories()."""
import unittest
from unittest.mock import Mock, patch

from speasy.core.requests_scheduling import request_dispatch as rd


class SafeInitProviderRetryTest(unittest.TestCase):
    def setUp(self):
        self._saved_amda = rd.amda
        self._saved_providers_entries = {name: rd.PROVIDERS[name] for name in ('amda',) if name in rd.PROVIDERS}

    def tearDown(self):
        rd.amda = self._saved_amda
        for name, value in self._saved_providers_entries.items():
            rd.PROVIDERS[name] = value

    def test_does_not_reconstruct_an_already_initialized_provider(self):
        rd.amda = Mock()
        with patch.object(rd, 'AmdaWebservice') as mock_cls:
            rd.init_amda()
        mock_cls.assert_not_called()

    def test_retries_a_provider_that_previously_failed_to_initialize(self):
        rd.amda = None
        fake_instance = Mock()
        with patch.object(rd, 'AmdaWebservice', return_value=fake_instance), \
             patch.object(rd, '_is_server_up', return_value=True):
            rd.init_amda()
        self.assertIs(rd.amda, fake_instance)
        self.assertIs(rd.PROVIDERS['amda'], fake_instance)


class UpdateInventoriesRetriesFailedProvidersTest(unittest.TestCase):
    def test_update_inventories_calls_init_providers_before_refreshing(self):
        # update_inventories() only ever refreshed providers already in PROVIDERS
        # (speasy.core.dataprovider.PROVIDERS), so a provider whose one-shot init at
        # import time failed (e.g. a transient error reaching its web service) was
        # never retried, ever, until the process restarted. init_providers() is a
        # no-op for every already-initialized provider (see _safe_init_provider), so
        # calling it again here is safe and just retries whatever is still missing.
        import speasy
        with patch.object(rd, 'init_providers') as mock_init_providers, \
             patch('speasy.core.dataprovider.PROVIDERS', {}):
            speasy.update_inventories()
        mock_init_providers.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
