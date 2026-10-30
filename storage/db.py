"""
SQLite storage backend.

Tables
------
snapshot        — M1: one row per monitor poll.
benchmark_result — M3+: output of every BenchmarkRunner.run() call.
applied_config  — M2+: audit trail of every sysctl write made by the controller.

Deliberately not using an ORM: this project's schema is small and stable,
and raw SQL keeps the storage layer auditable for the reproducibility story
your write-up needs.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from monitor.types import SystemSnapshot

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    cpu_util_pct REAL,
    ctxt_switches_total INTEGER,
    ctxt_switches_delta INTEGER,
    load_avg_1 REAL,
    load_avg_5 REAL,
    load_avg_15 REAL,
    runnable_procs INTEGER,
    total_procs INTEGER,
    mem_total_kb INTEGER,
    mem_available_kb INTEGER,
    mem_util_pct REAL,
    swap_total_kb INTEGER,
    swap_free_kb INTEGER,
    cpu_freq_mhz REAL,
    sched_params_json TEXT,
    numa_nodes_json TEXT,
    available_sources_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp ON snapshot(timestamp);

CREATE TABLE IF NOT EXISTS benchmark_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,          -- ISO-8601 UTC
    name TEXT NOT NULL,               -- adapter name, e.g. "stress-ng"
    workload_type TEXT NOT NULL,      -- "cpu" | "memory" | "io" | "mixed" | "interactive"
    success INTEGER NOT NULL,         -- 0 or 1
    score REAL NOT NULL,              -- primary metric
    score_is_higher_better INTEGER NOT NULL,
    metrics_json TEXT,                -- JSON dict of secondary metrics
    raw_output TEXT,                  -- full stdout/stderr for debugging
    error_message TEXT,
    tag TEXT                          -- optional free-text label, e.g. "pre-tuning"
);
CREATE INDEX IF NOT EXISTS idx_benchmark_timestamp ON benchmark_result(timestamp);
CREATE INDEX IF NOT EXISTS idx_benchmark_name      ON benchmark_result(name);

CREATE TABLE IF NOT EXISTS applied_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,          -- ISO-8601 UTC when the write happened
    param_name TEXT NOT NULL,         -- logical name from ParameterRegistry
    sysctl_path TEXT NOT NULL,        -- kernel.sched_* path
    old_value TEXT,                   -- value before the write (NULL if unknown)
    new_value TEXT NOT NULL,          -- value written and verified
    source TEXT,                      -- "controller" | "preset" | "profile:<name>"
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_config_timestamp ON applied_config(timestamp);
CREATE INDEX IF NOT EXISTS idx_config_param     ON applied_config(param_name);
"""


def _is_better(candidate: Dict[str, Any], current: Dict[str, Any]) -> bool:
    """Return True if *candidate* outranks *current* as a benchmark score."""
    if candidate["score_is_higher_better"]:
        return candidate["score"] > current["score"]
    return candidate["score"] < current["score"]


class StorageBackend:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path_str = str(db_path)
        # For on-disk paths create parent directories
        if self._db_path_str != ":memory:":
            Path(self._db_path_str).parent.mkdir(parents=True, exist_ok=True)
        # In-memory databases need a single persistent connection because
        # each sqlite3.connect(':memory:') call creates a fresh database.
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self._db_path_str == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        if self._mem_conn is not None:
            # Reuse the single in-memory connection; caller commits manually
            yield self._mem_conn
            self._mem_conn.commit()
        else:
            # timeout=10: wait up to 10 s if another writer holds the lock
            conn = sqlite3.connect(self._db_path_str, timeout=10)
            try:
                # WAL mode allows concurrent readers alongside one writer
                conn.execute("PRAGMA journal_mode=WAL")
                yield conn
                conn.commit()
            finally:
                conn.close()

    def write_snapshot(self, snapshot: SystemSnapshot) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO snapshot (
                    timestamp, cpu_util_pct, ctxt_switches_total,
                    ctxt_switches_delta, load_avg_1, load_avg_5, load_avg_15,
                    runnable_procs, total_procs, mem_total_kb,
                    mem_available_kb, mem_util_pct, swap_total_kb,
                    swap_free_kb, cpu_freq_mhz, sched_params_json,
                    numa_nodes_json, available_sources_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.timestamp.isoformat(),
                    snapshot.cpu_util_pct,
                    snapshot.ctxt_switches_total,
                    snapshot.ctxt_switches_delta,
                    snapshot.load_avg_1,
                    snapshot.load_avg_5,
                    snapshot.load_avg_15,
                    snapshot.runnable_procs,
                    snapshot.total_procs,
                    snapshot.mem_total_kb,
                    snapshot.mem_available_kb,
                    snapshot.mem_util_pct,
                    snapshot.swap_total_kb,
                    snapshot.swap_free_kb,
                    snapshot.cpu_freq_mhz,
                    json.dumps(snapshot.sched_params),
                    json.dumps(list(snapshot.numa_nodes)),
                    json.dumps(list(snapshot.available_sources)),
                ),
            )
            return cur.lastrowid

    def count_snapshots(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0]

    def recent_snapshots(self, limit: int = 10) -> list[sqlite3.Row]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM snapshot ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

    # ------------------------------------------------------------------
    # Benchmark results
    # ------------------------------------------------------------------

    def write_benchmark_result(
        self,
        name: str,
        workload_type: str,
        success: bool,
        score: float,
        score_is_higher_better: bool,
        metrics: Optional[Dict[str, Any]] = None,
        raw_output: str = "",
        error_message: str = "",
        tag: Optional[str] = None,
    ) -> int:
        """Persist one BenchmarkResult row. Returns the new row id."""
        ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO benchmark_result (
                    timestamp, name, workload_type, success, score,
                    score_is_higher_better, metrics_json, raw_output,
                    error_message, tag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    name,
                    workload_type,
                    int(success),
                    score,
                    int(score_is_higher_better),
                    json.dumps(metrics or {}),
                    raw_output,
                    error_message,
                    tag,
                ),
            )
            return cur.lastrowid

    def recent_benchmark_results(
        self, name: Optional[str] = None, limit: int = 50
    ) -> List[sqlite3.Row]:
        """Return the most recent benchmark results, optionally filtered by adapter name."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if name:
                return conn.execute(
                    "SELECT * FROM benchmark_result WHERE name=? ORDER BY id DESC LIMIT ?",
                    (name, limit),
                ).fetchall()
            return conn.execute(
                "SELECT * FROM benchmark_result ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

    def count_benchmark_results(self, name: Optional[str] = None) -> int:
        with self._connect() as conn:
            if name:
                return conn.execute(
                    "SELECT COUNT(*) FROM benchmark_result WHERE name=?", (name,)
                ).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM benchmark_result").fetchone()[0]

    def best_benchmark_for_category(
        self,
        category: str,
        *,
        limit: int = 500,
    ) -> Optional[Dict[str, Any]]:
        """Return the best historical benchmark row for a workload category.

        Matches rows where ``metrics_json.primary_category`` equals *category*
        or where ``workload_type`` matches the category's benchmark mapping.
        Returns a dict with keys: score, score_is_higher_better, sched_params,
        primary_category, workload_type, name, timestamp.
        """
        from workload.categories import CATEGORY_TO_BENCHMARK_TYPE

        target_type = CATEGORY_TO_BENCHMARK_TYPE.get(category, "mixed")
        rows = self.recent_benchmark_results(limit=limit)
        best: Optional[Dict[str, Any]] = None

        for row in rows:
            if not row["success"]:
                continue
            metrics = json.loads(row["metrics_json"] or "{}")
            row_category = metrics.get("primary_category")
            matches = (
                row_category == category
                or row["workload_type"] == target_type
            )
            if not matches:
                continue

            candidate = {
                "score": float(row["score"]),
                "score_is_higher_better": bool(row["score_is_higher_better"]),
                "sched_params": metrics.get("sched_params") or {},
                "primary_category": row_category or category,
                "workload_type": row["workload_type"],
                "name": row["name"],
                "timestamp": row["timestamp"],
            }
            if best is None or _is_better(candidate, best):
                best = candidate

        return best

    # ------------------------------------------------------------------
    # Applied config audit trail
    # ------------------------------------------------------------------

    def write_applied_config(
        self,
        param_name: str,
        sysctl_path: str,
        new_value: str,
        old_value: Optional[str] = None,
        source: str = "controller",
        success: bool = True,
        error_message: str = "",
    ) -> int:
        """Record one sysctl write in the audit trail. Returns the new row id."""
        ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO applied_config (
                    timestamp, param_name, sysctl_path, old_value,
                    new_value, source, success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    param_name,
                    sysctl_path,
                    old_value,
                    new_value,
                    source,
                    int(success),
                    error_message,
                ),
            )
            return cur.lastrowid

    def recent_applied_configs(
        self, param_name: Optional[str] = None, limit: int = 100
    ) -> List[sqlite3.Row]:
        """Return recent config writes, optionally filtered by parameter name."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if param_name:
                return conn.execute(
                    "SELECT * FROM applied_config WHERE param_name=? ORDER BY id DESC LIMIT ?",
                    (param_name, limit),
                ).fetchall()
            return conn.execute(
                "SELECT * FROM applied_config ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

    def count_applied_configs(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM applied_config").fetchone()[0]

    # ------------------------------------------------------------------
    # Sweep helpers
    # ------------------------------------------------------------------

    def best_params_for_workload(
        self,
        workload_type: str,
        *,
        tag_prefix: str = "sweep",
        limit: int = 2000,
    ) -> Optional[Dict[str, Any]]:
        """Return the scheduler param dict from the best sweep run for *workload_type*.

        Matches rows where ``tag`` starts with *tag_prefix* (default ``"sweep"``)
        and ``workload_type`` equals the argument.  Picks the single row with the
        best ``score`` (respecting ``score_is_higher_better``).

        Returns a dict with keys ``sched_params`` (dict), ``score``, ``name``,
        ``timestamp``, or *None* if no matching row exists.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM benchmark_result
                WHERE workload_type = ?
                  AND success = 1
                  AND tag LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (workload_type, f"{tag_prefix}%", limit),
            ).fetchall()

        if not rows:
            return None

        best_row = None
        best_score: Optional[float] = None
        higher_is_better = True

        for row in rows:
            metrics = json.loads(row["metrics_json"] or "{}")
            if tag_prefix == "sweep" and metrics.get("dry_run", False):
                continue
            sched_params = metrics.get("sched_params") or {}
            if not sched_params:
                continue
            score = float(row["score"])
            hib = bool(row["score_is_higher_better"])
            if best_score is None:
                best_row = row
                best_score = score
                higher_is_better = hib
            elif hib and score > best_score:
                best_row = row
                best_score = score
            elif not hib and score < best_score:
                best_row = row
                best_score = score

        if best_row is None:
            return None

        metrics = json.loads(best_row["metrics_json"] or "{}")
        return {
            "sched_params": metrics.get("sched_params") or {},
            "score": float(best_row["score"]),
            "score_is_higher_better": bool(best_row["score_is_higher_better"]),
            "name": best_row["name"],
            "workload_type": best_row["workload_type"],
            "timestamp": best_row["timestamp"],
        }

    def list_sweep_workload_types(self, tag_prefix: str = "sweep") -> List[str]:
        """Return distinct workload types that have at least one successful sweep row."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT workload_type FROM benchmark_result
                WHERE success = 1 AND tag LIKE ?
                """,
                (f"{tag_prefix}%",),
            ).fetchall()
        return [r[0] for r in rows]
