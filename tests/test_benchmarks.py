import pytest
from unittest.mock import patch, MagicMock
from benchmarks import StressNgAdapter, SysbenchAdapter, HackbenchAdapter, CyclictestAdapter, FioAdapter

def test_stress_ng_adapter_success():
    adapter = StressNgAdapter()
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        # Use the v0.21 'metrc:' format that stress-ng 0.21+ produces
        mock_proc.stderr = "stress-ng: metrc: [12345] cpu             2184     3.00      2.99      0.00      2184.09       2190.00"
        mock_run.return_value = mock_proc
        result = adapter.run(timeout=1, workers=1)
        assert result.success is True
        assert result.score == 2184.09
        assert result.score_is_higher_better is True
        assert result.metrics["bogo_ops"] == 2184.09

def test_sysbench_adapter_success():
    adapter = SysbenchAdapter()
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Total operations: 35081198 (3507119.54 per second)"
        mock_run.return_value = mock_proc
        result = adapter.run(timeout=1, threads=1)
        assert result.success is True
        assert result.score == 3507119.54
        assert result.metrics["ops_per_sec"] == 3507119.54

def test_hackbench_adapter_success():
    adapter = HackbenchAdapter()
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Time: 0.038"
        mock_run.return_value = mock_proc
        result = adapter.run(groups=1, loops=10)
        assert result.success is True
        assert result.score == 0.038
        assert result.score_is_higher_better is False
        assert result.metrics["time_sec"] == 0.038

def test_cyclictest_adapter_success():
    adapter = CyclictestAdapter()
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "T: 0 (12345) P: 0 I:1000 C:  10000 Min:      2 Act:    3 Avg:    4 Max:      15"
        mock_run.return_value = mock_proc
        result = adapter.run(loops=10)
        assert result.success is True
        assert result.score == 15.0
        assert result.score_is_higher_better is False
        assert result.metrics["avg_latency_us"] == 4.0
        assert result.metrics["max_latency_us"] == 15.0

def test_fio_adapter_success():
    adapter = FioAdapter()
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"jobs": [{"write": {"iops": 500.5, "bw": 2048000}}]}'
        mock_run.return_value = mock_proc
        result = adapter.run(size="10M")
        assert result.success is True
        assert result.score == 500.5
        assert result.score_is_higher_better is True
        assert result.metrics["write_iops"] == 500.5
        assert result.metrics["write_bw"] == 2048000.0

def test_adapter_not_found():
    adapter = HackbenchAdapter()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = adapter.run()
        assert result.success is False
        assert result.score == 0.0
