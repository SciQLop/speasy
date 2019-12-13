from spacepy import pycdf
import threading
from .variable import SpwcVariable


def tt2000_to_unix_epoch(variable: pycdf.Var):
    t = variable[:]
    return (t.astype('float64') / 1e9) + (
            pycdf.lib.tt2000_to_datetime(variable[0]).timestamp() - (t[0].astype('float64') / 1e9))


def cdf_epoch_to_unix_epoch(variable: pycdf.Var):
    t = variable[:]
    return (t.astype('float64') / 1e3) + (
            pycdf.lib.epoch_to_datetime(variable[0]).timestamp() - (t[0].astype('float64') / 1e3))


def convert_time(variable: pycdf.Var):
    typename = pycdf.lib.cdftypenames[variable.type()]
    if typename == 'CDF_TIME_TT2000':
        return tt2000_to_unix_epoch(variable)
    if typename == 'CDF_EPOCH':
        return cdf_epoch_to_unix_epoch(variable)


def get_depend(variable: pycdf.Var):
    if "DEPEND_0" in variable.attrs:
        return variable.attrs["DEPEND_0"]


def load_cdf(cdf_file, product):
    with threading.Lock() as lock:
        f = pycdf.CDF(cdf_file)
        if product in f:
            data_var = f[product]
            time_var = f.raw_var(get_depend(data_var))
            time = convert_time(time_var)
            return SpwcVariable(time=time, data=data_var[:], meta={}, columns=[], y=None)
        return None
