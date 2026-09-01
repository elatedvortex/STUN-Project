import pytest
import time
import os
import json
import threading
from unittest.mock import MagicMock
from safety import SecondaryValidator, Watchdog, CheckpointManager


# ── SecondaryValidator tests ─────────────────────────────────────────────

class TestSecondaryValidator:
    """Tests for the independent safety-layer validator (§4.2)."""

    def test_valid_value_within_limits(self):
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", 50000) is True

    def test_value_too_small(self):
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", 100) is False

    def test_value_too_large(self):
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", 2000000000) is False

    def test_unknown_path_allowed(self):
        """Unknown paths are allowed through — validator is a safety net, not a gatekeeper."""
        val = SecondaryValidator()
        assert val.validate("unknown.path", 123) is True

    def test_invalid_type_string(self):
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", "abc") is False

    def test_invalid_type_none(self):
        """None should be rejected for paths with hard limits."""
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", None) is False

    def test_boundary_values_min(self):
        """Exact minimum boundary should be accepted."""
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", 10000) is True

    def test_boundary_values_max(self):
        """Exact maximum boundary should be accepted."""
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", 1000000000) is True

    def test_just_below_min(self):
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", 9999) is False

    def test_just_above_max(self):
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", 1000000001) is False

    def test_negative_value_for_rt_runtime(self):
        """sched_rt_runtime_us allows -1 for unlimited (§1.4)."""
        val = SecondaryValidator()
        assert val.validate("kernel.sched_rt_runtime_us", -1) is True
        assert val.validate("kernel.sched_rt_runtime_us", -2) is False

    def test_all_known_params_have_limits(self):
        """Verify all 10 known params are covered (§1.4)."""
        val = SecondaryValidator()
        expected_paths = [
            "kernel.sched_min_granularity_ns",
            "kernel.sched_wakeup_granularity_ns",
            "kernel.sched_rr_timeslice_ms",
            "kernel.sched_rt_period_us",
            "kernel.sched_rt_runtime_us",
            "kernel.sched_cfs_bandwidth_slice_us",
            "kernel.sched_autogroup_enabled",
            "kernel.sched_util_clamp_max",
            "kernel.sched_util_clamp_min",
            "kernel.sched_schedstats",
        ]
        for path in expected_paths:
            assert path in val.hard_limits, f"Missing hard limit for {path}"

    def test_validate_batch_all_pass(self):
        val = SecondaryValidator()
        params = {
            "kernel.sched_min_granularity_ns": 50000,
            "kernel.sched_wakeup_granularity_ns": 50000,
        }
        assert val.validate_batch(params) is True

    def test_validate_batch_one_fails(self):
        val = SecondaryValidator()
        params = {
            "kernel.sched_min_granularity_ns": 50000,
            "kernel.sched_wakeup_granularity_ns": 1,  # too small
        }
        assert val.validate_batch(params) is False

    def test_extra_limits_extension(self):
        """Extra limits can be provided at construction time."""
        val = SecondaryValidator(extra_limits={"custom.param": (0, 100)})
        assert val.validate("custom.param", 50) is True
        assert val.validate("custom.param", 200) is False

    def test_float_string_values(self):
        """String representations of numbers should be parsed correctly."""
        val = SecondaryValidator()
        assert val.validate("kernel.sched_min_granularity_ns", "50000") is True
        assert val.validate("kernel.sched_min_granularity_ns", "100") is False


# ── Watchdog tests ───────────────────────────────────────────────────────

class TestWatchdog:
    """Tests for the watchdog timer (§4.2)."""

    def test_basic_ping_and_timeout(self):
        mock_rollback = MagicMock()
        wd = Watchdog(rollback_callback=mock_rollback, timeout_sec=0.2)

        wd.start()
        assert wd.running is True

        # Ping to keep alive
        wd.ping()
        time.sleep(0.1)
        mock_rollback.assert_not_called()

        # Let it timeout
        time.sleep(0.4)
        mock_rollback.assert_called_once()
        assert wd.running is False

    def test_stop_before_timeout(self):
        mock_rollback = MagicMock()
        wd = Watchdog(rollback_callback=mock_rollback, timeout_sec=1.0)

        wd.start()
        wd.stop()
        time.sleep(0.2)
        mock_rollback.assert_not_called()
        assert wd.running is False

    def test_multiple_start_calls_are_idempotent(self):
        mock_rollback = MagicMock()
        wd = Watchdog(rollback_callback=mock_rollback, timeout_sec=5.0)

        wd.start()
        wd.start()  # should be no-op
        wd.stop()
        assert wd.running is False

    def test_rollback_callback_exception_handled(self):
        """When rollback_callback raises, watchdog should handle gracefully (§4.2)."""
        def bad_callback():
            raise RuntimeError("simulated crash")

        wd = Watchdog(rollback_callback=bad_callback, timeout_sec=0.1)
        wd.start()
        time.sleep(0.4)
        # Should not crash — the watchdog catches the exception
        assert wd.running is False

    def test_thread_cleanup(self):
        """Watchdog thread should be a daemon and join properly."""
        mock_rollback = MagicMock()
        wd = Watchdog(rollback_callback=mock_rollback, timeout_sec=5.0)
        wd.start()

        assert wd._thread is not None
        assert wd._thread.daemon is True

        wd.stop()
        assert not wd._thread.is_alive()

    def test_thread_safety_concurrent_pings(self):
        """Concurrent pings from multiple threads should not crash (§1.3)."""
        mock_rollback = MagicMock()
        wd = Watchdog(rollback_callback=mock_rollback, timeout_sec=2.0)
        wd.start()

        errors = []
        def ping_loop():
            try:
                for _ in range(100):
                    wd.ping()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=ping_loop) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        wd.stop()
        assert len(errors) == 0, f"Concurrent pings raised errors: {errors}"


# ── CheckpointManager tests ─────────────────────────────────────────────

class TestCheckpointManager:
    """Tests for the crash-recovery checkpoint manager (§4.2, §4.3)."""

    def test_save_load_clear(self, tmp_path):
        """Uses tmp_path fixture instead of hardcoded /tmp (§4.3)."""
        path = str(tmp_path / "test_checkpoint.json")
        cm = CheckpointManager(checkpoint_path=path)

        # Empty load
        assert cm.load_checkpoint() == {}

        # Save
        cm.save_checkpoint({"a": 1, "b": "test"})
        assert os.path.exists(path)

        # Load
        assert cm.load_checkpoint() == {"a": 1, "b": "test"}

        # Clear
        cm.clear_checkpoint()
        assert not os.path.exists(path)

    def test_file_permissions(self, tmp_path):
        """Checkpoint file should be owner-only read/write (§6.2)."""
        path = str(tmp_path / "perm_test.json")
        cm = CheckpointManager(checkpoint_path=path)
        cm.save_checkpoint({"test": True})

        mode = os.stat(path).st_mode
        # Check owner read+write, no group/other
        assert mode & 0o600 == 0o600  # owner r+w
        assert mode & 0o077 == 0  # no group/other perms

    def test_corrupted_file_returns_empty(self, tmp_path):
        """Loading a corrupted JSON should return {} instead of crashing."""
        path = str(tmp_path / "corrupted.json")
        with open(path, 'w') as f:
            f.write("{invalid json!!!")

        cm = CheckpointManager(checkpoint_path=path)
        assert cm.load_checkpoint() == {}

    def test_overwrite_checkpoint(self, tmp_path):
        """Saving twice should overwrite cleanly."""
        path = str(tmp_path / "overwrite_test.json")
        cm = CheckpointManager(checkpoint_path=path)

        cm.save_checkpoint({"version": 1})
        assert cm.load_checkpoint() == {"version": 1}

        cm.save_checkpoint({"version": 2, "extra": "data"})
        assert cm.load_checkpoint() == {"version": 2, "extra": "data"}

    def test_clear_nonexistent_is_noop(self, tmp_path):
        """Clearing a non-existent checkpoint should not raise."""
        path = str(tmp_path / "nonexistent.json")
        cm = CheckpointManager(checkpoint_path=path)
        cm.clear_checkpoint()  # should not raise

    def test_nested_directory_creation(self, tmp_path):
        """CheckpointManager should create parent directories if needed."""
        path = str(tmp_path / "deep" / "nested" / "dir" / "ckpt.json")
        cm = CheckpointManager(checkpoint_path=path)
        cm.save_checkpoint({"nested": True})
        assert cm.load_checkpoint() == {"nested": True}
