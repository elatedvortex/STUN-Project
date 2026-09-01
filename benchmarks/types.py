from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class BenchmarkResult:
    """Normalized result structure for all benchmark adapters."""
    name: str                   # e.g., 'stress-ng', 'sysbench'
    workload_type: str          # e.g., 'cpu', 'memory', 'io', 'mixed'
    success: bool               # True if run completed without errors
    score: float                # Primary metric (higher is better, or lower is better depending on 'score_is_higher_better')
    score_is_higher_better: bool
    metrics: Dict[str, float] = field(default_factory=dict) # Raw secondary metrics
    raw_output: str = ""        # Full stdout/stderr for debugging
    error_message: str = ""
