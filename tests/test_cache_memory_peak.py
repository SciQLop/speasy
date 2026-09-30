import gc
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import numpy as np

POINTS_PER_SECOND = 20
FRAGMENT_HOURS = 12
REQUEST_HOURS = 48


def _synthetic_variable(start_time, stop_time):
    from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis
    n = int((stop_time - start_time).total_seconds() * POINTS_PER_SECOND)
    t0 = np.datetime64(start_time.replace(tzinfo=None), 'ns')
    time = t0 + (np.arange(n) * (1_000_000_000 // POINTS_PER_SECOND)).astype('timedelta64[ns]')
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)], values=DataContainer(values=np.random.random(n)))


def _proc_status_kb(field):
    with open("/proc/self/status") as f:
        return next(int(line.split()[1]) for line in f if line.startswith(field + ":"))


def _reset_peak_rss():
    # https://docs.kernel.org/filesystems/proc.html -- writing 5 to clear_refs resets VmHWM to the current RSS
    with open("/proc/self/clear_refs", "w") as f:
        f.write("5")


def _measure_warm_cached_read():
    from speasy.core.cache import Cache, Cacheable

    class Provider:
        @Cacheable(prefix="mem", cache_instance=Cache(tempfile.mkdtemp()), version=lambda self, product: 1,
                   fragment_hours=lambda product: FRAGMENT_HOURS)
        def get(self, product, start_time, stop_time):
            return _synthetic_variable(start_time, stop_time)

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = start + timedelta(hours=REQUEST_HOURS)
    provider = Provider()
    provider.get("synthetic", start, stop)
    # A first read fills the cache backend's own buffers, which then stay allocated and reused.
    provider.get("synthetic", start, stop)
    gc.collect()

    _reset_peak_rss()
    baseline_kb = _proc_status_kb("VmRSS")
    var = provider.get("synthetic", start, stop)
    peak_kb = _proc_status_kb("VmHWM") - baseline_kb
    return peak_kb, (var.values.nbytes + var.time.nbytes) / 1024


@unittest.skipUnless(sys.platform.startswith("linux") and platform.libc_ver()[0] == "glibc",
                     "peak RSS is read from /proc and the allocator is tuned through glibc")
class CachedReadMemoryPeak(unittest.TestCase):
    def test_warm_cache_read_peaks_near_result_size(self):
        # Real fragments are hundreds of MB, so glibc always mmaps them and returns them to the OS once freed.
        # Pinning the mmap threshold makes these small synthetic fragments behave the same way, and a subprocess
        # keeps that allocator setting and the peak RSS measurement away from the rest of the test session.
        env = {**os.environ, "MALLOC_MMAP_THRESHOLD_": str(1024 * 1024), "SPEASY_SKIP_INIT_PROVIDERS": "1"}
        out = subprocess.run([sys.executable, __file__], env=env, capture_output=True, text=True, check=True)
        peak_kb, result_kb = map(float, out.stdout.split()[-2:])

        fragment_kb = result_kb * FRAGMENT_HOURS / REQUEST_HOURS
        # Before the fix every fragment, including the cache margins, stayed alive next to the merged result: ~2.5x.
        self.assertLessEqual(peak_kb, result_kb + 4 * fragment_kb)


if __name__ == "__main__":
    print(*_measure_warm_cached_read())
