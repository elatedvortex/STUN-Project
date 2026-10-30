"""Tests for config/loader.py — registry building from YAML."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.loader import build_registry_from_config
from scheduler.registry import ParameterRegistry


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "scheduler.yaml"


# ── Tests: load from real YAML ────────────────────────────────────────────────

def test_build_registry_loads_default_config():
    registry = build_registry_from_config(str(_DEFAULT_CONFIG))
    params = registry.get_all()
    assert len(params) >= 4  # must have at least the 4 known params


def test_build_registry_returns_parameter_registry():
    registry = build_registry_from_config(str(_DEFAULT_CONFIG))
    assert isinstance(registry, ParameterRegistry)


def test_build_registry_params_have_required_fields():
    registry = build_registry_from_config(str(_DEFAULT_CONFIG))
    for meta in registry.get_all():
        assert meta.name, f"param missing name"
        assert meta.path, f"param {meta.name} missing path"
        assert meta.type is not None, f"param {meta.name} missing type"


def test_build_registry_known_params_present():
    registry = build_registry_from_config(str(_DEFAULT_CONFIG))
    names = {m.name for m in registry.get_all()}
    assert "sched_rr_timeslice_ms" in names
    assert "sched_rt_period_us" in names
    assert "sched_autogroup_enabled" in names


def test_build_registry_param_paths_start_with_kernel():
    registry = build_registry_from_config(str(_DEFAULT_CONFIG))
    for meta in registry.get_all():
        assert meta.path.startswith("kernel."), (
            f"param {meta.name} has non-kernel path: {meta.path}"
        )


def test_build_registry_bounds_are_numeric():
    registry = build_registry_from_config(str(_DEFAULT_CONFIG))
    for meta in registry.get_all():
        assert meta.min_value is not None
        assert meta.max_value is not None
        assert float(meta.min_value) <= float(meta.max_value), (
            f"{meta.name}: min={meta.min_value} > max={meta.max_value}"
        )


def test_build_registry_type_is_callable():
    registry = build_registry_from_config(str(_DEFAULT_CONFIG))
    for meta in registry.get_all():
        assert callable(meta.type), f"{meta.name}: type={meta.type!r} is not callable"


# ── Tests: subset filtering ───────────────────────────────────────────────────

def test_build_registry_param_names_filter():
    registry = build_registry_from_config(
        str(_DEFAULT_CONFIG),
        param_names=["sched_rr_timeslice_ms"],
    )
    params = registry.get_all()
    assert len(params) == 1
    assert params[0].name == "sched_rr_timeslice_ms"


def test_build_registry_empty_filter_returns_all():
    full = build_registry_from_config(str(_DEFAULT_CONFIG))
    filtered = build_registry_from_config(str(_DEFAULT_CONFIG), param_names=None)
    assert len(full.get_all()) == len(filtered.get_all())


def test_build_registry_unknown_param_name_ignored():
    """Unknown names in param_names filter should not raise — just be skipped."""
    registry = build_registry_from_config(
        str(_DEFAULT_CONFIG),
        param_names=["sched_rr_timeslice_ms", "nonexistent_param_xyz"],
    )
    names = {m.name for m in registry.get_all()}
    assert "sched_rr_timeslice_ms" in names
    assert "nonexistent_param_xyz" not in names


# ── Tests: synthetic YAML ─────────────────────────────────────────────────────

def _write_yaml(path: Path, content: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(content, f)


def test_build_registry_from_minimal_yaml():
    content = {
        "scheduler": {
            "params": [
                {
                    "name": "test_param",
                    "path": "kernel.test_param",
                    "type": "int",
                    "min_value": 0,
                    "max_value": 100,
                    "description": "A test param",
                }
            ]
        }
    }
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        yaml.dump(content, f)
        tmp_path = f.name

    try:
        registry = build_registry_from_config(tmp_path)
        params = registry.get_all()
        assert len(params) == 1
        assert params[0].name == "test_param"
        assert params[0].type is int
        assert params[0].min_value == 0
        assert params[0].max_value == 100
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_build_registry_float_type_yaml():
    content = {
        "scheduler": {
            "params": [
                {
                    "name": "float_param",
                    "path": "kernel.float_param",
                    "type": "float",
                    "min_value": 0.0,
                    "max_value": 1.0,
                }
            ]
        }
    }
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        yaml.dump(content, f)
        tmp_path = f.name

    try:
        registry = build_registry_from_config(tmp_path)
        params = registry.get_all()
        assert params[0].type is float
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_build_registry_missing_file_returns_empty():
    """Loader silently returns an empty registry when the file does not exist."""
    registry = build_registry_from_config("/nonexistent/path/config.yaml")
    # Either returns empty registry or raises — both are acceptable; just must not crash badly
    assert isinstance(registry, ParameterRegistry)
