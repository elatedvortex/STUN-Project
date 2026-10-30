"""Opt-in host checks: real reads and a one-second CPU benchmark; no writes."""
import os
import platform
import shutil

import pytest

from benchmarks.adapters import StressNgAdapter
from monitor.collector import Monitor, default_sources
from scheduler.backend import SysctlBackend

pytestmark = pytest.mark.skipif(os.environ.get("RUN_HOST_CHECKS") != "1",
                                reason="set RUN_HOST_CHECKS=1 for read-only host integration")


def test_real_sysctl_read():
    if not shutil.which("sysctl"):
        pytest.skip("sysctl unavailable")
    assert SysctlBackend().read("kernel.ostype") == platform.system()


def test_real_monitor_snapshot():
    monitor = Monitor(sources=default_sources())
    monitor.check_capabilities()
    snapshot = monitor.read_snapshot()
    assert snapshot.available_sources
    assert snapshot.mem_total_kb > 0


def test_real_cpu_benchmark_parser():
    if not shutil.which("stress-ng"):
        pytest.skip("stress-ng unavailable")
    result = StressNgAdapter().run(timeout=1, workers=1)
    assert result.success, result.error_message
    assert result.score > 0
