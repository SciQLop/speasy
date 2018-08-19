#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""

import pytest

from spwc.amda import amda
from datetime import datetime

'''
startdate=datetime(2006,1,8,1,0,0)
stopdate= datetime(2006,1,9,6,0,0)
parameterID = "c1_b_gsm"
'''

_get_param = [
        (datetime(2006,1,8,1,0,0), datetime(2006,1,8,1,0,1), "c1_b_gsm"),
        pytest.param(datetime(2006,1,8,1,0,0), datetime(2006,1,8,1,0,0), "c1_b_gsm",
                     marks=pytest.mark.xfail),
    ]


@pytest.mark.parametrize("start_date,stop_date,parameter_id", _get_param)
def test_amda_get_param_soap(start_date,stop_date,parameter_id):
    ws = amda.AMDA()
    data = ws.get_parameter(start_date, stop_date, parameter_id, method="SOAP")
    assert(data is not None)


@pytest.mark.parametrize("start_date,stop_date,parameter_id", _get_param)
def test_amda_get_param_rest(start_date,stop_date,parameter_id):
    ws = amda.AMDA()
    data = ws.get_parameter(start_date, stop_date, parameter_id,method="REST")
    assert(data is not None)
