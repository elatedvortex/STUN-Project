"""Unit tests for workload/classifier.py and workload/categories.py."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor.types import SystemSnapshot, ProcessInfo
from workload.classifier import ProcessClassifier
from workload.categories import CATEGORY_TO_BENCHMARK_TYPE, WORKLOAD_CATEGORIES


# ── Helpers ───────────────────────────────────────────────────────────────────

def _snap(*comms, cpu=30.0):
    procs = tuple(
        ProcessInfo(pid=i + 1, comm=c, state="R", utime=1000, stime=100, num_threads=2)
        for i, c in enumerate(comms)
    )
    return SystemSnapshot(
        timestamp=datetime.now(timezone.utc),
        processes=procs,
        cpu_util_pct=cpu,
        load_avg_1=1.0,
        mem_util_pct=40.0,
    )


# ── Tests: category constants ─────────────────────────────────────────────────

def test_all_workload_categories_non_empty():
    assert len(WORKLOAD_CATEGORIES) > 0
    for cat in WORKLOAD_CATEGORIES:
        assert isinstance(cat, str) and cat


def test_category_to_benchmark_type_covers_all_categories():
    """Every workload category must map to a benchmark type."""
    for cat in WORKLOAD_CATEGORIES:
        btype = CATEGORY_TO_BENCHMARK_TYPE.get(cat)
        assert btype is not None, f"Missing mapping for category {cat!r}"


def test_benchmark_types_are_known_values():
    known_types = {"cpu", "memory", "io", "interactive", "gaming", "mixed"}
    for cat, btype in CATEGORY_TO_BENCHMARK_TYPE.items():
        assert btype in known_types, f"{cat!r} maps to unknown type {btype!r}"


# ── Tests: ProcessClassifier ──────────────────────────────────────────────────

def test_classifier_gaming_detection():
    snap = _snap("steam", "wine")
    fp = ProcessClassifier().fingerprint(snap)
    assert fp.primary_category == "gaming"


def test_classifier_compiler_detection():
    snap = _snap("gcc", "make", "cc1")
    fp = ProcessClassifier().fingerprint(snap)
    assert fp.primary_category == "compiler"


def test_classifier_browser_detection():
    snap = _snap("chrome", "chromium")
    fp = ProcessClassifier().fingerprint(snap)
    assert fp.primary_category in ("browser", "interactive")


def test_classifier_database_detection():
    # postgres → "database"; mysqld was previously misclassified as "compiler"
    # due to `ld` substring match — regression test for that bug fix
    snap = _snap("postgres", "redis")
    fp = ProcessClassifier().fingerprint(snap)
    assert fp.primary_category == "database"


def test_classifier_mysqld_not_misclassified_as_compiler():
    """Regression: mysqld contains 'ld' but must not match compiler pattern."""
    snap = _snap("mysqld")
    fp = ProcessClassifier().fingerprint(snap)
    assert fp.primary_category == "database", (
        f"mysqld was misclassified as {fp.primary_category!r} (ld-substring bug)"
    )


def test_classifier_empty_processes():
    snap = _snap()
    fp = ProcessClassifier().fingerprint(snap)
    # Should not crash; primary_category should be some string
    assert isinstance(fp.primary_category, str)


def test_classifier_top_processes_populated():
    snap = _snap("gcc", "make", "ld")
    fp = ProcessClassifier().fingerprint(snap)
    assert len(fp.top_processes) > 0
    # Each entry is a (comm, score) tuple
    comm, score = fp.top_processes[0]
    assert isinstance(comm, str)


def test_classifier_benchmark_workload_type_is_valid():
    known_types = {"cpu", "memory", "io", "interactive", "gaming", "mixed"}
    for comms in [("steam",), ("gcc",), ("postgres",), ("bash",)]:
        snap = _snap(*comms)
        fp = ProcessClassifier().fingerprint(snap)
        assert fp.benchmark_workload_type in known_types, (
            f"comms={comms} → unexpected type {fp.benchmark_workload_type!r}"
        )


def test_classifier_python_script_category():
    snap = _snap("python", "python3")
    fp = ProcessClassifier().fingerprint(snap)
    # Python could be anything; just ensure it doesn't crash and returns valid type
    assert isinstance(fp.primary_category, str)
    assert isinstance(fp.benchmark_workload_type, str)


def test_classifier_unknown_process_falls_back_to_default():
    snap = _snap("xyzzy_unknown_process_12345")
    fp = ProcessClassifier().fingerprint(snap)
    assert isinstance(fp.primary_category, str)


# ── Tests: fingerprint fields ─────────────────────────────────────────────────

def test_fingerprint_has_required_fields():
    snap = _snap("gcc")
    fp = ProcessClassifier().fingerprint(snap)
    assert hasattr(fp, "primary_category")
    assert hasattr(fp, "top_processes")
    assert hasattr(fp, "benchmark_workload_type")


def test_classifier_is_deterministic():
    snap = _snap("gcc", "make")
    clf = ProcessClassifier()
    fp1 = clf.fingerprint(snap)
    fp2 = clf.fingerprint(snap)
    assert fp1.primary_category == fp2.primary_category
    assert fp1.benchmark_workload_type == fp2.benchmark_workload_type


def test_interval_activity_outweighs_old_idle_process():
    from dataclasses import replace
    snapshot = _snap("chrome", "gcc")
    snapshot = replace(snapshot, processes=(
        replace(snapshot.processes[0], utime=1_000_000, cpu_ticks_delta=0),
        replace(snapshot.processes[1], utime=100, cpu_ticks_delta=20),
    ))
    fp = ProcessClassifier().fingerprint(snapshot)
    assert fp.primary_category == "compiler"
    assert fp.measurement_basis == "interval"
    assert fp.category_weights["browser"] == 0


def test_unknown_cpu_activity_reduces_classification_coverage():
    from dataclasses import replace
    snapshot = _snap("gcc", "unknown-compute-job")
    snapshot = replace(snapshot, processes=tuple(
        replace(proc, cpu_ticks_delta=weight)
        for proc, weight in zip(snapshot.processes, [1, 99])
    ))
    fp = ProcessClassifier().fingerprint(snapshot)
    assert fp.classified_cpu_fraction == pytest.approx(0.01)
