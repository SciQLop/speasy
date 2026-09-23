#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the chunked download of `speasy.core.impex.ImpexProvider`."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np

from speasy.core.impex import ImpexProvider
from speasy.core.impex.exceptions import FailedChunkedRequest
from speasy.products.variable import SpeasyVariable, VariableTimeAxis, DataContainer

START = datetime(2020, 1, 1, tzinfo=timezone.utc)
CHUNK_DAYS = 10


def _one_point_per_day(start: datetime, stop: datetime) -> SpeasyVariable:
    days = np.arange(np.datetime64(start.replace(tzinfo=None), 'ns'),
                     np.datetime64(stop.replace(tzinfo=None), 'ns'), np.timedelta64(1, 'D'))
    return SpeasyVariable(axes=[VariableTimeAxis(values=days)],
                          values=DataContainer(values=np.ones((len(days), 1))), columns=['x'])


def _provider_whose_chunks_fail_at(failing_chunk_starts):
    def is_private_parameter(parameter_id):
        return False

    def _dl_parameter_chunk(start_time, stop_time, parameter_id, **kwargs):
        if start_time in failing_chunk_starts:
            return None
        return _one_point_per_day(start_time, stop_time)

    return SimpleNamespace(provider_name="test", max_chunk_size_days=CHUNK_DAYS,
                           _dl_parameter_chunk=_dl_parameter_chunk, is_private_parameter=is_private_parameter)


def _download(provider, days: int):
    return ImpexProvider._dl_parameter(provider, start_time=START, stop_time=START + timedelta(days=days),
                                       parameter_id='some_param')


class ImpexChunkedDownload(unittest.TestCase):
    def test_all_chunks_succeeding_gives_the_whole_range(self):
        var = _download(_provider_whose_chunks_fail_at([]), days=3 * CHUNK_DAYS)
        self.assertEqual(len(var), 3 * CHUNK_DAYS)

    def test_a_single_failed_chunk_fails_the_whole_request(self):
        # A partial result would be cached as covering the whole range,
        # leaving permanent empty fragments where the failed chunk was.
        middle_chunk = START + timedelta(days=CHUNK_DAYS)
        provider = _provider_whose_chunks_fail_at([middle_chunk])
        with self.assertRaises(FailedChunkedRequest):
            _download(provider, days=3 * CHUNK_DAYS)


if __name__ == '__main__':
    unittest.main()
